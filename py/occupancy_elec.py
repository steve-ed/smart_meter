"""
Electricity-based occupancy detector.

Infers OCCUPIED / VACANT / UNKNOWN labels from half-hourly electricity
consumption using an always-on floor approach. Slots into the Tier 3
signal fusion stack at positions 4.5 (OCCUPIED) and 6.5 (VACANT).

See docs/superpowers/specs/2026-07-20-occupancy-electricity-design.md
"""

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OVERNIGHT_PERIODS    = frozenset(range(2, 11))  # 01:00–05:30 (period indices 2–10)
FLOOR_PERCENTILE     = 20
MIN_NIGHTS           = 14
COLD_START_FLOOR_KWH = 0.030

OCCUPIED_EXCESS_KWH  = 0.05
OCCUPIED_SOFT_KWH    = 0.025

VACANT_RATIO         = 1.40
VACANT_MIN_PERIODS   = 6

HEATING_GUARD_KWH    = 0.50
HEATING_GUARD_TEMP_C = 7.0

FLOOR_STABILITY_PCT  = 0.25
FLOOR_STEP_WEEKS     = 3
ROLLING_WEEKS        = 8

_SOFT_PENDING = '_soft_pending'  # internal marker, cleaned up before returning

# ---------------------------------------------------------------------------
# Floor computation
# ---------------------------------------------------------------------------

def compute_floor(samples):
    """Return (floor_kwh at P20, floor_mad) from a list of kWh readings."""
    if not samples:
        return (0.0, 0.0)
    s = sorted(samples)
    n = len(s)
    idx = max(0, int(n * FLOOR_PERCENTILE / 100))
    floor = s[idx]
    raw_mad = sorted(abs(v - floor) for v in s)[n // 2]
    return (floor, max(raw_mad, 0.005))


# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------

def is_heating_contaminated(overnight_median_kwh, outdoor_temp_c):
    """True when electric heating is likely corrupting the overnight floor."""
    return overnight_median_kwh > HEATING_GUARD_KWH and outdoor_temp_c < HEATING_GUARD_TEMP_C


def compute_thresholds(floor_kwh, floor_mad):
    """Return (hard_threshold_kwh, soft_threshold_kwh) for OCCUPIED detection."""
    hard = floor_kwh + max(OCCUPIED_EXCESS_KWH, 3.0 * floor_mad)
    soft = floor_kwh + max(OCCUPIED_SOFT_KWH,  1.5 * floor_mad)
    return (hard, soft)


# ---------------------------------------------------------------------------
# Sequence labeller
# ---------------------------------------------------------------------------

def label_sequence(elec_kwh, floor_kwh, floor_mad,
                   heating_contaminated=False, in_cold_start=False):
    """
    Label 48 half-hourly periods as OCCUPIED / VACANT / UNKNOWN.

    floor_source and floor_stable in output are placeholder values
    ('overnight_bootstrap', True) — overwrite them from ElecOccupancyDetector.
    """
    if in_cold_start:
        hard_thresh = COLD_START_FLOOR_KWH + OCCUPIED_EXCESS_KWH
        soft_thresh = None
    else:
        hard_thresh, soft_thresh = compute_thresholds(floor_kwh, floor_mad)

    results = []
    soft_run = 0
    floor_run = 0
    floor_run_start = -1
    vacant_active = False

    for i, kwh in enumerate(elec_kwh):
        is_overnight = i in OVERNIGHT_PERIODS
        above_hard = kwh >= hard_thresh
        above_soft = (not in_cold_start) and (soft_thresh is not None) and (kwh >= soft_thresh)
        at_floor_raw = kwh <= floor_kwh * VACANT_RATIO
        # Suppress at-floor vacancy overnight when electric heating is contaminating the floor
        at_floor = at_floor_raw and not (heating_contaminated and is_overnight)

        label = 'UNKNOWN'
        label_source = None

        if above_hard:
            label = 'OCCUPIED'
            label_source = 'elec_above_floor_hard'
            soft_run = 0
            floor_run = 0
            floor_run_start = -1
            vacant_active = False

        elif above_soft:
            soft_run += 1
            floor_run = 0
            floor_run_start = -1
            if soft_run >= 2:
                label = 'OCCUPIED'
                label_source = 'elec_above_floor_soft'
                vacant_active = False
                if results and results[-1]['label_source'] == _SOFT_PENDING:
                    results[-1]['occupied_label'] = 'OCCUPIED'
                    results[-1]['label_source'] = 'elec_above_floor_soft'
            else:
                label = 'UNKNOWN'
                label_source = _SOFT_PENDING

        elif at_floor:
            soft_run = 0
            if floor_run_start == -1:
                floor_run_start = i
            floor_run += 1
            if vacant_active:
                label = 'VACANT'
                label_source = 'elec_at_floor'
            elif floor_run >= VACANT_MIN_PERIODS:
                label = 'VACANT'
                label_source = 'elec_at_floor'
                vacant_active = True
                for j in range(floor_run_start, i):
                    results[j]['occupied_label'] = 'VACANT'
                    results[j]['label_source'] = 'elec_at_floor'
            else:
                label = 'UNKNOWN'

        else:
            soft_run = 0
            floor_run = 0
            floor_run_start = -1
            vacant_active = False

        results.append({
            'period_index':         i,
            'elec_kwh':             kwh,
            'floor_kwh':            floor_kwh,
            'floor_mad_kwh':        floor_mad,
            'floor_source':         'overnight_bootstrap',
            'floor_stable':         True,
            'heating_contaminated': heating_contaminated,
            'at_floor':             at_floor_raw,  # raw comparison; heating suppression reflected in occupied_label only
            'occupied_label':       label,
            'label_source':         label_source,
            'sustained_run':        floor_run if at_floor else (soft_run if above_soft else 0),
        })

    for r in results:
        if r['label_source'] == _SOFT_PENDING:
            r['label_source'] = None

    return results


# ---------------------------------------------------------------------------
# Stateful detector
# ---------------------------------------------------------------------------

class ElecOccupancyDetector:
    """Maintains a rolling always-on floor and labels periods day by day."""

    def __init__(self):
        self._overnight_samples = []
        self._days_accumulated = 0
        self._prior_floor = None
        self._unstable_weeks = 0
        self._outdoor_temps = []

        self.floor_kwh = 0.0
        self.floor_mad = 0.005
        self.floor_source = 'overnight_bootstrap'
        self.floor_stable = True
        self.floor_step_change = False
        self.heating_contaminated = False

    @property
    def in_cold_start(self):
        return self._days_accumulated < MIN_NIGHTS

    def add_day(self, date_str, elec_kwh_48, outdoor_temp_c, confirmed_vacant=None):
        """
        Process one day of 48 half-hourly readings.

        date_str: 'YYYY-MM-DD'
        elec_kwh_48: list of 48 floats
        outdoor_temp_c: daily outdoor temperature
        confirmed_vacant: list of (period_index, kwh) from higher-priority sensor signals
        Returns: list of 48 period dicts matching the output schema.
        """
        for p in OVERNIGHT_PERIODS:
            self._overnight_samples.append(elec_kwh_48[p])
        self._days_accumulated += 1

        max_samples = ROLLING_WEEKS * 7 * len(OVERNIGHT_PERIODS)
        if len(self._overnight_samples) > max_samples:
            self._overnight_samples = self._overnight_samples[-max_samples:]

        # Update floor at cold-start exit and every 7 days thereafter
        if (self._days_accumulated == MIN_NIGHTS or
                (not self.in_cold_start and self._days_accumulated % 7 == 0)):
            self._update_floor(confirmed_vacant)

        # Rolling 14-day outdoor temperature for heating guard
        self._outdoor_temps.append(outdoor_temp_c)
        if len(self._outdoor_temps) > 14:
            self._outdoor_temps = self._outdoor_temps[-14:]

        if len(self._outdoor_temps) >= 7 and self._overnight_samples:
            n_recent = 7 * len(OVERNIGHT_PERIODS)
            recent_overnight = self._overnight_samples[-n_recent:]
            overnight_med = sorted(recent_overnight)[len(recent_overnight) // 2]
            outdoor_med = sorted(self._outdoor_temps)[len(self._outdoor_temps) // 2]
            self.heating_contaminated = is_heating_contaminated(overnight_med, outdoor_med)

        labels = label_sequence(
            elec_kwh=elec_kwh_48,
            floor_kwh=self.floor_kwh,
            floor_mad=self.floor_mad,
            heating_contaminated=self.heating_contaminated,
            in_cold_start=self.in_cold_start,
        )
        for r in labels:
            r['floor_source'] = self.floor_source
            r['floor_stable'] = self.floor_stable

        return labels

    def _update_floor(self, confirmed_vacant=None):
        if confirmed_vacant:
            samples = [kwh for _, kwh in confirmed_vacant]
            self.floor_source = 'sensor_calibrated'
            new_floor, new_mad = compute_floor(samples)
        else:
            self.floor_source = 'overnight_bootstrap'
            # Use full rolling window for the stable floor value
            new_floor, new_mad = compute_floor(self._overnight_samples)
            # Assess stability using only the most recent week's samples
            week_n = 7 * len(OVERNIGHT_PERIODS)
            recent = self._overnight_samples[-week_n:]
            candidate_floor, _ = compute_floor(recent)

        if self._prior_floor is not None:
            # For sensor_calibrated, compare directly; for overnight, compare recent candidate
            compare_floor = new_floor if confirmed_vacant else candidate_floor
            change = abs(compare_floor - self._prior_floor) / max(self._prior_floor, 1e-6)
            if change > FLOOR_STABILITY_PCT:
                self._unstable_weeks += 1
                self.floor_stable = False
                if self._unstable_weeks >= FLOOR_STEP_WEEKS:
                    # Accept the step change using the candidate floor (new regime)
                    accepted_floor = new_floor if confirmed_vacant else candidate_floor
                    accepted_mad = new_mad if confirmed_vacant else compute_floor(
                        self._overnight_samples[-(7 * len(OVERNIGHT_PERIODS)):]
                    )[1]
                    self.floor_kwh = accepted_floor
                    self.floor_mad = accepted_mad
                    self.floor_step_change = True
                    self._unstable_weeks = 0
                    self.floor_stable = True
                    self._prior_floor = accepted_floor
                return   # hold previous value until step change confirmed
            else:
                self._unstable_weeks = 0
                self.floor_stable = True

        self.floor_kwh = new_floor
        self.floor_mad = new_mad
        self._prior_floor = new_floor

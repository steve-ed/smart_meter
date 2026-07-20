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

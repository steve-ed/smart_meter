# Tier 3 — Occupancy-Dependent Services: Implementation Guide

Services covered:
- **#11** Vacancy-Aware Anomaly Suppression
- **#12** Standby and Phantom Load Detection

---

## 1. Data Model

### Half-hourly interval structure

Smart meter data arrives as discrete half-hourly readings. Each reading represents energy consumed during that 30-minute window, not an instantaneous power reading.

```
period_index : int        # 0–47 (0 = 00:00–00:30, 47 = 23:30–24:00)
timestamp    : datetime   # start of the period (UTC)
elec_kwh     : float      # electricity consumed in this half-hour (kWh)
gas_kwh      : float      # gas consumed in this half-hour (kWh), if metered
```

A full day is 48 periods. A week is 336 periods. Annual baseline requires ≥ 17,520 periods.

### Derived power

For algorithm clarity, power in watts can be derived when needed:

```
power_w = elec_kwh * 2000   # kWh per 30 min → average Watts
```

This is only a convenience; the source unit is always kWh per half-hour.

### Timestamps and alignment

All occupancy events must be mapped to the same half-hourly grid before joining with meter data. An occupancy event at 14:47 maps to period 29 (14:30–15:00). The rule is: **floor to the nearest 30-minute boundary**.

```python
def to_period_index(ts: datetime) -> int:
    return ts.hour * 2 + ts.minute // 30
```

---

## 2. Occupancy Detection Layer

Tier 3 requires one or more occupancy signals. Each produces a per-period occupancy label.

### Occupancy states

```
OCCUPIED   — at least one person confirmed present
VACANT     — property confirmed empty
UNKNOWN    — no signal available for this period
```

`UNKNOWN` is important: do not treat it as either OCCUPIED or VACANT. Services that need confirmed occupancy must explicitly handle UNKNOWN.

### Signal sources and mapping

**PIR sensor**

PIR fires on motion detection, not continuous presence. The mapping rule: a PIR trigger in period *p* marks periods *p* and *p+1* as OCCUPIED (a motion event at 14:47 implies presence for at least an hour in most residential contexts). A chain of PIR triggers with no gap > 90 minutes is treated as a continuous OCCUPIED block.

```python
def pir_to_occupancy(pir_events: list[datetime], periods: int = 48) -> list[str]:
    labels = ['UNKNOWN'] * periods
    for event in pir_events:
        p = to_period_index(event)
        for offset in range(3):          # mark p, p+1, p+2 (90 min)
            if p + offset < periods:
                labels[p + offset] = 'OCCUPIED'
    # fill VACANT only if no OCCUPIED label exists anywhere today
    # (PIR cannot confirm VACANT — only OCCUPIED or UNKNOWN)
    return labels
```

PIR alone cannot confirm VACANT. A period with no PIR trigger is UNKNOWN, not VACANT.

**CO₂ sensor (preferred)**

CO₂ is the most reliable passive occupancy proxy. Background outdoor CO₂ is approximately 420 ppm. Occupied indoor air rises above 600–700 ppm within one to two half-hour periods of a person being present.

```
threshold_occupied : 650 ppm     # above → OCCUPIED
threshold_vacant   : 520 ppm     # below for ≥ 3 consecutive periods → VACANT
hysteresis_periods : 3           # require 3 consecutive periods before flipping
```

CO₂ sensor readings are continuous; map to half-hourly by averaging all readings within the period window.

```python
def co2_to_occupancy(co2_readings: dict[datetime, float]) -> dict[int, str]:
    # co2_readings: {timestamp: ppm}
    period_avgs = aggregate_to_half_hourly(co2_readings, method='mean')
    labels = {}
    state = 'UNKNOWN'
    consecutive = 0

    for period_idx in sorted(period_avgs):
        ppm = period_avgs[period_idx]
        if ppm >= 650:
            state = 'OCCUPIED'
            consecutive = 0
        elif ppm <= 520:
            consecutive += 1
            if consecutive >= 3:
                state = 'VACANT'
        else:
            consecutive = 0
        labels[period_idx] = state

    return labels
```

**Phone presence (WiFi/BT)**

Device presence on the home network is a high-confidence signal when detected. Map to half-hourly:
- Device seen in period → OCCUPIED
- No device seen for ≥ 6 consecutive periods (3 hours) → VACANT
- Gap < 6 periods → UNKNOWN (phone may be off/sleeping, not absent)

Multi-person households require OR logic: OCCUPIED if any registered device is present.

**Calendar / manual away mode**

User-declared absence (holiday mode, away dates) produces confirmed VACANT blocks. These override sensor signals and fill gaps reliably. Store as `[start_datetime, end_datetime)` intervals and expand to half-hourly labels.

### Signal fusion

When multiple signals are available, fuse using this priority:

```
1. Manual away calendar       → VACANT (highest confidence)
2. CO₂ ≥ threshold            → OCCUPIED
3. Phone presence confirmed   → OCCUPIED
4. PIR trigger                → OCCUPIED
5. CO₂ < threshold (sustained)→ VACANT
6. Phone absent (sustained)   → VACANT
7. No signal                  → UNKNOWN
```

Conflicts: if CO₂ says OCCUPIED but phone says absent, prefer CO₂ (phone may have died or left the house briefly).

Store the fused label per period alongside its source for auditability.

---

## 3. Service #11 — Vacancy-Aware Anomaly Suppression

### Problem

Anomaly detectors flag flat-lines (unexpectedly zero consumption) and spikes (unexpectedly high consumption). Without occupancy context, they produce two failure modes:

- **False positive (flat-line):** household on holiday for two weeks, detector fires daily because gas is zero
- **False negative (spike):** large consumption event occurs while vacant; suppressed because the system doesn't know it matters more, not less

Occupancy context eliminates both.

### Anomaly taxonomy with occupancy

| Anomaly type | Occupancy state | Interpretation | Action |
|---|---|---|---|
| Flat-line (elec) | OCCUPIED | Meter fault, supply outage, or circuit issue | Alert: high priority |
| Flat-line (elec) | VACANT | Expected (away) | Suppress |
| Flat-line (elec) | UNKNOWN | Ambiguous | Alert: low priority after 48h |
| Flat-line (gas) | OCCUPIED, winter | Boiler fault or no heating demand | Alert if outdoor temp < 10°C |
| Flat-line (gas) | OCCUPIED, summer | Normal (no heating) | Suppress |
| Flat-line (gas) | VACANT | Expected | Suppress |
| Spike (elec) | OCCUPIED | Unusual high-draw event | Alert: medium priority |
| Spike (elec) | VACANT | Unexpected activity (security concern, fault) | Alert: high priority |
| Spike (gas) | OCCUPIED | Heating demand spike | Alert if > 3σ above seasonal norm |
| Spike (gas) | VACANT | Leak, pilot light, or rogue heating | Alert: high priority |

### Flat-line detection algorithm

A flat-line is defined as an unbroken run of periods where consumption falls below a minimum threshold.

```python
FLAT_THRESHOLD_ELEC = 0.010   # kWh per half-hour (~20W — below any realistic occupied baseline)
FLAT_THRESHOLD_GAS  = 0.005   # kWh per half-hour
MIN_FLAT_PERIODS    = 6       # 3 consecutive hours before classifying as flat-line

def detect_flatline(readings: list[float], threshold: float, min_periods: int) -> list[tuple[int, int]]:
    """Return list of (start_period, end_period) for each flat-line run."""
    runs = []
    run_start = None

    for i, val in enumerate(readings):
        if val < threshold:
            if run_start is None:
                run_start = i
        else:
            if run_start is not None and (i - run_start) >= min_periods:
                runs.append((run_start, i - 1))
            run_start = None

    if run_start is not None and (len(readings) - run_start) >= min_periods:
        runs.append((run_start, len(readings) - 1))

    return runs
```

For gas, apply a seasonal suppression guard before running the flat-line detector. In summer months (May–September), gas flat-lines during OCCUPIED periods are normal (no space heating). Only alert on gas flat-lines in the heating season (October–April) when outdoor temperature is below 12°C.

### Spike detection algorithm

Spikes are detected relative to a household-specific baseline, not a global threshold. This accounts for high-consumption households (large families, EVs, heat pumps) that would otherwise generate constant false positives.

**Baseline construction:**

For each of the 336 period slots in a week (48 periods × 7 days), compute a rolling baseline from the prior 8 weeks of the same slot.

```python
def build_baseline(history: dict[tuple[int,int], list[float]]) -> dict[tuple[int,int], tuple[float, float]]:
    """
    history: {(weekday, period_index): [kwh readings for this slot over 8 weeks]}
    Returns: {(weekday, period_index): (median, mad)}
    """
    baseline = {}
    for slot, values in history.items():
        arr = sorted(values)
        med = arr[len(arr) // 2]
        mad = sorted(abs(v - med) for v in arr)[len(arr) // 2]
        baseline[slot] = (med, mad)
    return baseline
```

Use MAD (median absolute deviation) rather than standard deviation. Half-hourly energy data is not normally distributed — it is right-skewed with occasional legitimate outliers. MAD is robust to those.

**Spike threshold:**

```
spike_threshold = median + k * mad

k = 4.0   (conservative; adjust down to 3.0 for more sensitive alerting)
```

A MAD of zero (the slot is always identical, e.g., always-zero overnight) gets a minimum floor of 0.05 kWh to prevent division-by-zero and over-sensitivity.

**Spike classification with occupancy:**

```python
def classify_spike(reading: float, baseline_median: float, baseline_mad: float,
                   occupancy: str, k: float = 4.0) -> str | None:
    mad = max(baseline_mad, 0.05)
    threshold = baseline_median + k * mad

    if reading <= threshold:
        return None   # not a spike

    if occupancy == 'VACANT':
        return 'SPIKE_VACANT'      # unexpected; high priority
    elif occupancy == 'OCCUPIED':
        return 'SPIKE_OCCUPIED'    # unusual but explainable; medium priority
    else:
        return 'SPIKE_UNKNOWN'     # low priority
```

### Occupancy integration

Wrap both detectors with occupancy lookup:

```python
def evaluate_period(period_idx: int, date: date, reading: float,
                    occupancy_labels: dict[int, str],
                    baseline: dict[tuple[int,int], tuple[float, float]],
                    prior_flat_count: int,
                    commodity: str) -> dict:

    occupancy = occupancy_labels.get(period_idx, 'UNKNOWN')
    weekday = date.weekday()
    med, mad = baseline.get((weekday, period_idx), (0.1, 0.05))
    threshold = 'FLAT_THRESHOLD_ELEC' if commodity == 'elec' else 'FLAT_THRESHOLD_GAS'

    result = {
        'period': period_idx,
        'occupancy': occupancy,
        'reading_kwh': reading,
        'alerts': []
    }

    # flat-line check
    flat_thresh = 0.010 if commodity == 'elec' else 0.005
    if reading < flat_thresh:
        new_flat_count = prior_flat_count + 1
        if new_flat_count >= 6:
            if occupancy == 'OCCUPIED':
                result['alerts'].append({'type': 'FLATLINE', 'priority': 'HIGH', 'suppress': False})
            elif occupancy == 'VACANT':
                result['alerts'].append({'type': 'FLATLINE', 'priority': 'HIGH', 'suppress': True})
            else:  # UNKNOWN
                if new_flat_count >= 48:   # 24h before alerting on UNKNOWN
                    result['alerts'].append({'type': 'FLATLINE', 'priority': 'LOW', 'suppress': False})
    else:
        new_flat_count = 0

    # spike check
    spike = classify_spike(reading, med, max(mad, 0.05), occupancy)
    if spike:
        priority = 'HIGH' if spike == 'SPIKE_VACANT' else 'MEDIUM'
        result['alerts'].append({'type': spike, 'priority': priority, 'suppress': False})

    result['flat_run_length'] = new_flat_count
    return result
```

### Alert deduplication

Suppress duplicate alerts for the same event. An ongoing flat-line spanning 48 periods should produce one alert, not 48. Track active alert state per household per commodity:

```
alert_open    : bool
alert_type    : str
alert_start   : datetime
alert_last_period : int
```

Open a new alert when an anomaly starts. Update `alert_last_period` each period while it continues. Close and resolve when the anomaly clears. Only fire a notification at open time and at close time.

---

## 4. Service #12 — Standby and Phantom Load Detection

### Problem

When the property is confirmed VACANT, any electricity consumption is either:
- **Always-on baseline:** fridges, routers, alarm systems, smart meters — unavoidable
- **Phantom load:** TVs/consoles on standby, phone chargers left plugged in, forgotten appliances

The service quantifies both, identifies when phantom load is elevated above the household's own historical VACANT baseline, and benchmarks against a peer group.

### Vacancy baseline construction

Only use periods with confirmed VACANT occupancy (not UNKNOWN). Exclude the first and last two periods of any vacancy block — these transition periods may contain departure and arrival activity that inflates the apparent standby load.

```python
def build_vacancy_baseline(readings: list[tuple[datetime, float, str]]) -> dict:
    """
    readings: [(timestamp, elec_kwh, occupancy_label)]
    Returns baseline statistics for VACANT periods.
    """
    vacant_kwh = []
    blocks = extract_vacancy_blocks(readings)   # list of [period, ...] groups

    for block in blocks:
        # trim first and last 2 periods (1 hour)
        trimmed = block[2:-2] if len(block) > 4 else block
        vacant_kwh.extend(p['elec_kwh'] for p in trimmed)

    if len(vacant_kwh) < 48:   # need at least 24h of confirmed vacancy
        return None

    vacant_kwh.sort()
    n = len(vacant_kwh)
    return {
        'median_kwh':    vacant_kwh[n // 2],
        'p10_kwh':       vacant_kwh[n // 10],
        'p90_kwh':       vacant_kwh[int(n * 0.9)],
        'p95_kwh':       vacant_kwh[int(n * 0.95)],
        'sample_periods': n,
        'always_on_floor_kwh': vacant_kwh[n // 10],   # P10 is the irreducible baseline
    }
```

The **P10** value represents the true always-on floor — the minimum realistic standby consumption. The **median** is the typical standby level including minor phantom loads. The **P90** and above represent periods with elevated phantom loads.

### Phantom load classification

For each VACANT period, classify the reading against the household's own baseline:

```python
def classify_vacant_period(elec_kwh: float, baseline: dict) -> str:
    if elec_kwh <= baseline['p10_kwh'] * 1.1:
        return 'ALWAYS_ON'        # within 10% of floor: unavoidable
    elif elec_kwh <= baseline['p90_kwh']:
        return 'LOW_PHANTOM'      # above floor but within normal scatter
    elif elec_kwh <= baseline['p95_kwh']:
        return 'ELEVATED_PHANTOM' # worth investigating
    else:
        return 'HIGH_PHANTOM'     # significant forgotten-on appliance likely
```

### Annualised phantom load estimate

```python
def annual_phantom_cost(baseline: dict, unit_rate_p_per_kwh: float) -> dict:
    always_on_kwh_year    = baseline['always_on_floor_kwh'] * 17520
    typical_standby_year  = baseline['median_kwh'] * 17520
    phantom_kwh_year      = (baseline['median_kwh'] - baseline['always_on_floor_kwh']) * 17520

    return {
        'always_on_kwh_year':   round(always_on_kwh_year, 1),
        'phantom_kwh_year':     round(phantom_kwh_year, 1),
        'phantom_cost_gbp_year': round(phantom_kwh_year * unit_rate_p_per_kwh / 100, 2),
        'typical_total_kwh_year': round(typical_standby_year, 1),
    }
```

17,520 = 48 periods × 365 days. This assumes the standby load is constant; in practice, vacancy hours vary seasonally. For a more accurate estimate, weight by the fraction of periods that are VACANT in each season.

### Trend detection

Track the rolling 4-week median VACANT consumption. A statistically significant upward trend indicates a new always-on device has been added (new appliance left plugged in, new fridge, etc.).

```python
def detect_standby_trend(weekly_medians: list[float], threshold_pct: float = 20.0) -> bool:
    """
    weekly_medians: list of median VACANT kWh per half-hour for each of the past 8 weeks
    Returns True if a step change upward has occurred.
    """
    if len(weekly_medians) < 4:
        return False

    baseline_window = weekly_medians[:4]
    recent_window   = weekly_medians[4:]

    baseline_med = sorted(baseline_window)[2]
    recent_med   = sorted(recent_window)[len(recent_window) // 2]

    pct_change = (recent_med - baseline_med) / max(baseline_med, 0.001) * 100
    return pct_change > threshold_pct
```

A step change of > 20% in the VACANT median that persists for 2+ weeks is a reliable signal of a new permanent load.

### Peer benchmarking

Group households by property type and number of bedrooms. For each group, compute the distribution of VACANT median consumption across all consenting meters.

```
peer_group_key = (property_type, bedrooms)
# e.g., ('semi-detached', 3)
```

Peer percentile ranks allow consumer-facing messaging:

```python
def peer_percentile(household_median: float, peer_medians: list[float]) -> int:
    below = sum(1 for m in peer_medians if m < household_median)
    return int(below / len(peer_medians) * 100)
```

Consumer output example:
> "Your typical standby load is 0.14 kWh per half-hour. 73% of similar 3-bedroom semis have a lower standby load."

### ELEVATED_PHANTOM alert logic

Only fire an alert when the elevated phantom load is sustained (not a single period) and the magnitude exceeds a meaningful threshold:

```python
def should_alert_phantom(current_block_kwh: list[float], baseline: dict) -> bool:
    # require at least 4 consecutive ELEVATED or HIGH periods (2 hours)
    if len(current_block_kwh) < 4:
        return False

    elevated_count = sum(
        1 for v in current_block_kwh
        if v > baseline['p90_kwh']
    )

    if elevated_count < 4:
        return False

    # require excess above P10 floor to be at least 0.05 kWh (100W equivalent) per period
    excess = [v - baseline['always_on_floor_kwh'] for v in current_block_kwh]
    return sum(excess) / len(excess) >= 0.05
```

A sustained 100W phantom load over a two-week holiday costs approximately £3–5 and is worth surfacing. A single anomalous period is not.

---

## 5. Implementation Notes

### Minimum data requirements

| Service | Minimum history | Minimum vacancy evidence |
|---|---|---|
| #11 Anomaly suppression | 8 weeks (for baseline) | Any confirmed occupancy signal |
| #12 Phantom load | 4 weeks | ≥ 48 confirmed VACANT periods (24h) |

Below these thresholds, operate in a degraded mode: suppress anomaly suppression logic (default to current detector behaviour) and do not display phantom load estimates until sufficient vacancy data is accumulated.

### Handling UNKNOWN periods in service #12

Do not include UNKNOWN periods in the VACANT baseline. An UNKNOWN period where consumption is high could be occupied (normal) rather than phantom load. Including UNKNOWN periods would inflate the baseline median and mask genuine phantom loads.

### DST transitions

Twice per year, the half-hourly grid has 46 or 50 periods rather than 48. Meter data providers typically handle this by either duplicating a period or skipping one. Validate period counts and flag days with ≠ 48 periods before analysis to avoid off-by-one errors in period index lookups.

### Cold-start problem

New households have no history. Bootstrap the spike detection baseline using:
1. Similar households in the peer group (property type, bedrooms, occupant count)
2. National half-hourly demand shape scaled to the household's total daily consumption
3. Switch to household-specific baseline once 8 weeks of data are available

For the VACANT baseline, cold-start is less critical — the first confirmed vacancy period (even a single night away) provides a usable floor. Build up the full baseline over subsequent vacancies.

### Privacy and consent

Occupancy data is significantly more sensitive than energy data alone. Inferred occupancy reveals:
- Whether the property is occupied at any given time
- Sleep patterns
- Holiday and away patterns

Treat occupancy labels as a derived sensitive attribute. Do not expose raw occupancy labels via API. Aggregate or anonymise before any cross-household benchmarking. Require explicit opt-in consent separately from the base energy data consent.

---

## 6. Output Schema

### Anomaly alert

```json
{
  "household_id": "...",
  "alert_id": "...",
  "type": "FLATLINE | SPIKE_OCCUPIED | SPIKE_VACANT | SPIKE_UNKNOWN",
  "commodity": "elec | gas",
  "priority": "HIGH | MEDIUM | LOW",
  "suppressed": false,
  "suppress_reason": null,
  "start_period": "2026-07-15T02:00:00Z",
  "end_period": null,
  "reading_kwh": 0.0,
  "baseline_median_kwh": 0.12,
  "baseline_mad_kwh": 0.03,
  "occupancy_state": "OCCUPIED",
  "occupancy_source": "co2_sensor"
}
```

### Phantom load report (weekly)

```json
{
  "household_id": "...",
  "report_week": "2026-07-14",
  "vacancy_periods_available": 96,
  "always_on_floor_kwh_per_period": 0.048,
  "median_vacant_kwh_per_period":   0.142,
  "phantom_kwh_per_period":         0.094,
  "phantom_kwh_annualised":         1645.0,
  "phantom_cost_gbp_annualised":    394.80,
  "unit_rate_p_per_kwh":            24.0,
  "peer_percentile": 73,
  "trend_alert": false,
  "elevated_phantom_blocks": []
}
```

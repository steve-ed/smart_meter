# Tier 3 Service #11 — Vacancy-Aware Anomaly Suppression Design Spec

Date: 2026-07-24

## Overview

Service #11 detects electricity flat-line and spike anomalies and applies occupancy-based suppression to eliminate false positives. A flat-line during a confirmed vacancy is expected; one during occupied hours is a fault. Spike during vacancy is a security/fault concern; spike during occupation is unusual but often explainable.

Outputs a CSV of alert events (one row per anomaly, deduplicated across periods).

## Architecture

Two files:

- **`py/tier3_lib.py`** — shared occupancy-loading foundation. Wraps `ElecOccupancyDetector` from `occupancy_elec.py`. Returns per-day labeled periods for a configurable window. Reused by Service #12.
- **`py/s11_anomaly_suppression.py`** — flat-line detection, spike detection, occupancy suppression, alert deduplication, CSV output.

Pattern follows tier1/tier2: stdlib only, CSV output to `data/`, pure functions tested in `tests/`.

## Decisions

| Decision | Choice |
|---|---|
| Commodity | Electricity only (gas deferred) |
| Analysis window | Last 8 weeks of data in consumption.csv |
| Warm-up window | 8 weeks before analysis window (occupancy floor calibration + spike baseline) |
| Occupancy signal | `ElecOccupancyDetector` only (no PIR/CO₂/phone data available) |
| Flat-line threshold | 0.010 kWh/period (~20W — below any realistic occupied baseline) |
| Flat-line min duration | 6 periods (3 hours) |
| Spike k-factor | 4.0 (conservative) |
| MAD floor | 0.05 kWh (prevents over-sensitivity on always-zero slots) |
| Alert deduplication | Flat-lines emit one row when they close; spikes are per-period |

---

## File Structure

```
py/
  tier3_lib.py                   # shared occupancy loader
  s11_anomaly_suppression.py     # Service #11

data/
  s11_anomaly_suppression.csv    # output

tests/
  test_tier3_lib.py
  test_s11_anomaly_suppression.py
```

---

## `tier3_lib.py` — Shared Foundation

### `load_labeled_days`

```python
def load_labeled_days(
    meter_id: int,
    weeks: int = 16,
) -> list[dict]
```

Returns a list of day-dicts for the most recent `weeks` weeks of complete data, in chronological order:

```python
{
    "date":    str,        # "YYYY-MM-DD"
    "weekday": int,        # 0=Mon … 6=Sun
    "periods": list[dict], # 48 items — output of ElecOccupancyDetector.add_day()
}
```

Each period dict (from `ElecOccupancyDetector`) contains at minimum:
- `period_index: int`
- `elec_kwh: float`
- `occupied_label: str`  — `"OCCUPIED"`, `"VACANT"`, or `"UNKNOWN"`
- `floor_kwh: float`

Callers split the returned list into warm-up and analysis windows as needed. For example, with `weeks=16`, `all_days[-8*7:]` is the analysis window and `all_days[:-8*7]` is the baseline window.

**Implementation steps:**
1. Call `load_electricity(meter_id)` from `tier1_lib` to get all electricity readings
2. Call `load_weather()` from `tier2_lib`; compute daily mean temperature per date
3. Determine the cutoff: `latest_date − weeks × 7`
4. Filter electricity readings to `[cutoff, latest_date]`; build daily 48-element arrays; skip days with < 48 readings
5. Feed all days in order to a fresh `ElecOccupancyDetector` via `add_day(date, elec_48, outdoor_temp_c)`
6. Return all processed days

---

## `s11_anomaly_suppression.py` — Service #11

### Pure functions

**`detect_flatlines(elec_48: list[float], threshold: float = 0.010, min_periods: int = 6) → list[tuple[int, int]]`**

Returns `[(start_period, end_period), ...]` for each contiguous run where `elec_kwh < threshold` lasting ≥ `min_periods`. End period is inclusive.

**`build_spike_baseline(days: list[dict]) → dict[tuple[int, int], tuple[float, float]]`**

Takes the full set of labeled days (warm-up + analysis). For each `(weekday, period_index)` slot, computes `(median_kwh, mad_kwh)` from all historical readings in that slot. MAD is floored at `0.05` kWh.

```python
# returns {(weekday, period_index): (median, mad)}
```

**`classify_spike(reading: float, median: float, mad: float, occupancy: str, k: float = 4.0) → str | None`**

Threshold = `median + k × max(mad, 0.05)`. Returns:
- `None` if `reading ≤ threshold`
- `"SPIKE_VACANT"` if occupancy == `"VACANT"`
- `"SPIKE_OCCUPIED"` if occupancy == `"OCCUPIED"`
- `"SPIKE_UNKNOWN"` if occupancy == `"UNKNOWN"`

**`apply_occupancy_suppression(alert_type: str, occupancy: str) → dict`**

Returns `{"priority": str, "suppressed": bool, "suppress_reason": str | None}`.

| alert_type | occupancy | priority | suppressed | suppress_reason |
|---|---|---|---|---|
| FLATLINE | OCCUPIED | HIGH | False | None |
| FLATLINE | VACANT | HIGH | True | "vacancy" |
| FLATLINE | UNKNOWN | LOW | False | None |
| SPIKE_VACANT | VACANT | HIGH | False | None |
| SPIKE_OCCUPIED | OCCUPIED | MEDIUM | False | None |
| SPIKE_UNKNOWN | UNKNOWN | LOW | False | None |

### Alert deduplication

Flat-lines may span multiple periods or cross midnight into subsequent days. The `main()` loop tracks open flat-line state across days:

- Open: when a flat-line run starts (first period below threshold in a qualifying run)
- Close + emit row: when consumption rises above threshold or the analysis window ends

Each spike period is its own alert row (spikes are point events, not sustained runs).

### main()

```
1. For each meter_id in METERS:
   a. load_labeled_days(meter_id, weeks=16) → all_days
   b. Split: analysis_days = all_days[-56:]  (last 8 weeks × 7 days)
   c. build_spike_baseline(all_days)         (uses full 16 weeks for baseline)
   d. Walk analysis_days day by day:
      - detect_flatlines on the day's 48 readings
      - for each period: classify_spike, apply_occupancy_suppression
      - manage open flat-line state across days
      - collect alert rows
2. Write s11_anomaly_suppression.csv
```

### CSV output

File: `data/s11_anomaly_suppression.csv`

Columns:
```
meter_id, alert_type, priority, suppressed, suppress_reason, occupancy_state,
start_date, start_period, end_date, end_period, duration_periods,
mean_kwh, baseline_median_kwh, baseline_mad_kwh
```

One row per alert event. `end_date`/`end_period` are the last period of the anomaly (inclusive). `mean_kwh` is the mean reading across all periods in the event. For spikes, `duration_periods = 1` and `start == end`.

### Console output

One line per meter:
```
M1: 12 alerts (3 suppressed) — 5 flatline, 7 spike
```

---

## Tests

### `tests/test_tier3_lib.py`

Smoke-level only — verifies the module imports cleanly and `load_occupancy_for_window` is callable. No file I/O in unit tests.

### `tests/test_s11_anomaly_suppression.py`

Covers all four pure functions:

**detect_flatlines:**
- Single qualifying run detected
- Two separate runs detected
- Run below `min_periods` not returned
- Run exactly at `min_periods` returned
- All values above threshold → empty list

**build_spike_baseline:**
- Correct median and mad per `(weekday, period)` slot
- MAD floored at 0.05 when all readings identical (zero MAD)
- Multiple weekdays produce separate entries

**classify_spike:**
- Below threshold → `None`
- Above threshold, each occupancy state → correct type
- MAD floor applied when mad < 0.05

**apply_occupancy_suppression:**
- All six combinations from the table above

~15 tests total.

---

## Data Requirements

| Source | Used for |
|---|---|
| `data/consumption.csv` | Electricity readings (via `load_electricity`) |
| `data/weather.csv` | Daily mean temperature for occupancy detector |
| `data/tariff.csv` | Not used in #11 |

Minimum history: 16 weeks of electricity data (8 warm-up + 8 analysis). Meters with less history skip gracefully with a console message.

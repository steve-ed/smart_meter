# Tier 2 Weather Services Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build six Python service scripts (#5–#10 from `docs/tier2_weather.md`) that produce console summaries and CSV outputs using existing smart meter and weather data.

**Architecture:** Shared library `py/tier2_lib.py` provides HDD regression, data loaders, and utilities. Six focused service scripts (`s05_`–`s10_`) each import from it. Scripts run from project root (`python py/s06_heating_efficiency.py`). Outputs go to `data/`.

**Tech Stack:** Python 3.10+, stdlib only (`csv`, `math`, `datetime`, `statistics`, `urllib.request`). No pandas. Tests with pytest.

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `py/config.py` | Modify | Add `CARBON_REGION_ID`, `METER_META` |
| `py/tier4_analysis.py` | Modify | Import `METER_META` from config instead of defining it |
| `py/tier2_lib.py` | Create | Shared HDD regression, data loaders, utilities |
| `py/s05_boiler_trending.py` | Create | Service #5 — boiler efficiency trending |
| `py/s06_heating_efficiency.py` | Create | Service #6 — heating efficiency scoring |
| `py/s07_budget_forecast.py` | Create | Service #7 — degree-day budget forecasting |
| `py/s08_carbon_shifting.py` | Create | Service #8 — carbon-aware demand shifting |
| `py/s09_prewarm.py` | Create | Service #9 — heating pre-warm optimisation |
| `py/s10_leak_frost.py` | Create | Service #10 — micro-leak and frost detection |
| `data/appliances.csv` | Create | User-editable appliance list for Service #8 |
| `tests/test_tier2_lib.py` | Create | Tests for shared library |
| `tests/test_s05_boiler_trending.py` | Create | Tests for s05 pure functions |
| `tests/test_s06_heating_efficiency.py` | Create | Tests for s06 pure functions |
| `tests/test_s07_budget_forecast.py` | Create | Tests for s07 pure functions |
| `tests/test_s08_carbon_shifting.py` | Create | Tests for s08 pure functions |
| `tests/test_s09_prewarm.py` | Create | Tests for s09 pure functions |
| `tests/test_s10_leak_frost.py` | Create | Tests for s10 pure functions |

---

## Task 1: Update config.py and tier4_analysis.py

**Files:**
- Modify: `py/config.py`
- Modify: `py/tier4_analysis.py`

- [ ] **Step 1: Add constants to config.py**

Append to `py/config.py`:

```python
# ---------------------------------------------------------------------------
# Carbon intensity API
# ---------------------------------------------------------------------------

CARBON_REGION_ID = 12   # West Yorkshire DNO region (National Grid ESO)

# ---------------------------------------------------------------------------
# Meter metadata (property type / build era for HDD benchmarking)
# ---------------------------------------------------------------------------

METER_META = {
    1: {"property_type": "semi",     "build_era": "1945_1980"},
    2: {"property_type": "semi",     "build_era": "post_1980"},
    3: {"property_type": "detached", "build_era": "post_1980"},
    4: {"property_type": "terraced", "build_era": "pre_1945"},
    5: {"property_type": "semi",     "build_era": "post_1980"},
}
```

- [ ] **Step 2: Update tier4_analysis.py to import METER_META from config**

In `py/tier4_analysis.py`, find the existing `METER_META` definition (around line 46):

```python
METER_META = {
    1: {"property_type": "semi",     "build_era": "1945_1980"},
    2: {"property_type": "semi",     "build_era": "post_1980"},
    3: {"property_type": "detached", "build_era": "post_1980"},
    4: {"property_type": "terraced", "build_era": "pre_1945"},
    5: {"property_type": "semi",     "build_era": "post_1980"},
}
```

Replace it with:

```python
from config import METER_META  # noqa: F401 – re-exported for backward compat
```

And add `METER_META` to the existing `from config import (...)` block at the top of the file.

- [ ] **Step 3: Verify tier4_analysis.py still imports correctly**

```bash
cd /c/Users/steve/projects/smart_meter
python -c "from py.tier4_analysis import METER_META; print('ok')"
```

Or from inside `py/`:

```bash
python -c "import sys; sys.path.insert(0,'py'); from tier4_analysis import METER_META; print(METER_META)"
```

Expected: dict with 5 entries printed.

- [ ] **Step 4: Commit**

```bash
git add py/config.py py/tier4_analysis.py
git commit -m "feat: add CARBON_REGION_ID and METER_META to config; import in tier4_analysis"
```

---

## Task 2: tier2_lib.py — Shared Foundation

**Files:**
- Create: `py/tier2_lib.py`
- Create: `tests/test_tier2_lib.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_tier2_lib.py`:

```python
import pytest
from tier2_lib import (
    daily_hdd, period_hdd, effective_temp,
    fit_hdd_regression,
    period_to_time, time_to_period,
    UK_BENCHMARKS, benchmark_percentile,
)


# --- daily_hdd ---

def test_daily_hdd_cold():
    assert daily_hdd(5.0) == pytest.approx(10.5)

def test_daily_hdd_warm():
    assert daily_hdd(20.0) == 0.0

def test_daily_hdd_at_base():
    assert daily_hdd(15.5) == 0.0


# --- period_hdd ---

def test_period_hdd_cold():
    assert period_hdd(5.0) == pytest.approx(10.5 / 48)

def test_period_hdd_warm():
    assert period_hdd(20.0) == 0.0


# --- effective_temp ---

def test_effective_temp_no_wind():
    assert effective_temp(10.0, 1.0) == pytest.approx(10.0)

def test_effective_temp_at_threshold():
    assert effective_temp(10.0, 2.0) == pytest.approx(10.0)

def test_effective_temp_with_wind():
    # (5.0 - 2.0) / 3.0 * 0.5 = 0.5 reduction
    assert effective_temp(10.0, 5.0) == pytest.approx(9.5)


# --- fit_hdd_regression ---

def test_fit_hdd_regression_perfect_line():
    # slope=10, intercept=5: gas = 10*hdd + 5
    records = [(1.0, 15.0), (2.0, 25.0), (3.0, 35.0), (4.0, 45.0)]
    slope, intercept, r_sq = fit_hdd_regression(records)
    assert slope == pytest.approx(10.0, abs=1e-6)
    assert intercept == pytest.approx(5.0, abs=1e-6)
    assert r_sq == pytest.approx(1.0, abs=1e-6)

def test_fit_hdd_regression_r_squared_below_one():
    records = [(1.0, 15.0), (2.0, 26.0), (3.0, 34.0), (4.0, 46.0)]
    slope, intercept, r_sq = fit_hdd_regression(records)
    assert 0.0 < r_sq < 1.0

def test_fit_hdd_regression_too_few_points():
    slope, intercept, r_sq = fit_hdd_regression([(5.0, 50.0)])
    assert slope == 0.0
    assert intercept == 0.0
    assert r_sq == 0.0

def test_fit_hdd_regression_slope_non_negative():
    # Inverted data that would give a negative slope — must clamp to 0
    records = [(1.0, 50.0), (2.0, 40.0), (3.0, 30.0)]
    slope, intercept, r_sq = fit_hdd_regression(records)
    assert slope >= 0.0


# --- period_to_time ---

def test_period_to_time_midnight():
    assert period_to_time(0) == "00:00"

def test_period_to_time_half_past_midnight():
    assert period_to_time(1) == "00:30"

def test_period_to_time_seven_am():
    assert period_to_time(14) == "07:00"

def test_period_to_time_last_period():
    assert period_to_time(47) == "23:30"


# --- time_to_period ---

def test_time_to_period_midnight():
    assert time_to_period(0, 0) == 0

def test_time_to_period_seven_am():
    assert time_to_period(7, 0) == 14

def test_time_to_period_half_hour():
    assert time_to_period(0, 30) == 1

def test_time_to_period_last():
    assert time_to_period(23, 30) == 47


# --- benchmark_percentile ---

def test_benchmark_at_median():
    result = benchmark_percentile(23.0, "semi", "post_1980")
    assert result["percentile"] == pytest.approx(50.0)
    assert result["band"] == "average"

def test_benchmark_at_p25_efficient():
    result = benchmark_percentile(17.0, "semi", "post_1980")
    assert result["percentile"] == pytest.approx(25.0)
    assert result["band"] == "efficient"

def test_benchmark_at_p75_inefficient():
    result = benchmark_percentile(30.0, "semi", "post_1980")
    assert result["percentile"] == pytest.approx(75.0)
    assert result["band"] == "inefficient"

def test_benchmark_unknown_type():
    result = benchmark_percentile(20.0, "bungalow", "pre_1945")
    assert result["percentile"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /c/Users/steve/projects/smart_meter
python -m pytest tests/test_tier2_lib.py -v 2>&1 | head -20
```

Expected: `ImportError: No module named 'tier2_lib'`

- [ ] **Step 3: Create py/tier2_lib.py**

```python
"""
Shared foundation for Tier 2 weather service scripts.
Not run directly — imported by s05_*.py through s10_*.py.
"""

import csv
import math
from datetime import date, datetime

from config import GAS_KWH_PER_M3, GAS_CAP_M3, METERS

# ---------------------------------------------------------------------------
# HDD constants
# ---------------------------------------------------------------------------

BASE_TEMP_C = 15.5   # UK Met Office standard base temperature

# ---------------------------------------------------------------------------
# HDD functions
# ---------------------------------------------------------------------------

def daily_hdd(mean_temp_c: float) -> float:
    return max(BASE_TEMP_C - mean_temp_c, 0.0)


def period_hdd(temp_c: float) -> float:
    return max(BASE_TEMP_C - temp_c, 0.0) / 48


def effective_temp(temp_c: float, wind_speed_ms: float) -> float:
    if wind_speed_ms <= 2.0:
        return temp_c
    adjustment = (wind_speed_ms - 2.0) / 3.0 * 0.5
    return temp_c - adjustment


# ---------------------------------------------------------------------------
# HDD regression
# ---------------------------------------------------------------------------

def fit_hdd_regression(records: list[tuple[float, float]]) -> tuple[float, float, float]:
    """
    OLS fit on [(hdd, gas_kwh)] pairs.
    Returns (slope, intercept, r_squared).
    Clamps slope and intercept to >= 0.
    """
    n = len(records)
    if n < 2:
        return 0.0, 0.0, 0.0
    sx  = sum(r[0] for r in records)
    sy  = sum(r[1] for r in records)
    sxx = sum(r[0] ** 2 for r in records)
    sxy = sum(r[0] * r[1] for r in records)
    denom = n * sxx - sx * sx
    if abs(denom) < 1e-9:
        return 0.0, max(sy / n, 0.0), 0.0
    slope     = (n * sxy - sx * sy) / denom
    intercept = (sy - slope * sx) / n
    slope     = max(slope, 0.0)
    intercept = max(intercept, 0.0)
    y_mean = sy / n
    ss_tot = sum((r[1] - y_mean) ** 2 for r in records)
    ss_res = sum((r[1] - (slope * r[0] + intercept)) ** 2 for r in records)
    r_sq   = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return slope, intercept, r_sq


# ---------------------------------------------------------------------------
# Period utilities
# ---------------------------------------------------------------------------

def period_to_time(period_index: int) -> str:
    hour   = period_index // 2
    minute = (period_index % 2) * 30
    return f"{hour:02d}:{minute:02d}"


def time_to_period(hour: int, minute: int) -> int:
    return hour * 2 + minute // 30


# ---------------------------------------------------------------------------
# Peer benchmarks — kWh/HDD by (property_type, build_era)
# Source: NEED dataset (BEIS), values from docs/tier2_weather.md
# ---------------------------------------------------------------------------

UK_BENCHMARKS: dict[tuple[str, str], tuple[float, float, float]] = {
    # key: (median kWh/HDD, p25, p75)
    ("detached",   "pre_1945"):  (55.0, 42.0, 72.0),
    ("detached",   "1945_1980"): (42.0, 33.0, 54.0),
    ("detached",   "post_1980"): (30.0, 22.0, 40.0),
    ("semi",       "pre_1945"):  (40.0, 31.0, 52.0),
    ("semi",       "1945_1980"): (32.0, 25.0, 42.0),
    ("semi",       "post_1980"): (23.0, 17.0, 30.0),
    ("terraced",   "pre_1945"):  (35.0, 27.0, 46.0),
    ("terraced",   "1945_1980"): (28.0, 21.0, 37.0),
    ("terraced",   "post_1980"): (20.0, 15.0, 27.0),
    ("flat",       "pre_1945"):  (25.0, 18.0, 33.0),
    ("flat",       "1945_1980"): (20.0, 14.0, 28.0),
    ("flat",       "post_1980"): (14.0, 10.0, 19.0),
}


def benchmark_percentile(kwh_per_hdd: float,
                          property_type: str,
                          build_era: str) -> dict:
    key = (property_type, build_era)
    if key not in UK_BENCHMARKS:
        return {"percentile": None, "reason": "no_benchmark_available"}
    median, p25, p75 = UK_BENCHMARKS[key]
    if kwh_per_hdd <= p25:
        pct = 25 * kwh_per_hdd / p25
    elif kwh_per_hdd <= median:
        pct = 25 + 25 * (kwh_per_hdd - p25) / (median - p25)
    elif kwh_per_hdd <= p75:
        pct = 50 + 25 * (kwh_per_hdd - median) / (p75 - median)
    else:
        pct = 75 + 25 * min((kwh_per_hdd - p75) / p75, 1.0)
    band = "efficient" if pct < 33 else "average" if pct < 67 else "inefficient"
    return {
        "household_kwh_per_hdd": round(kwh_per_hdd, 1),
        "peer_median_kwh_per_hdd": median,
        "percentile": round(pct, 0),
        "band": band,
    }


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

def load_weather(path: str = "data/weather.csv") -> list[dict]:
    """Return half-hourly weather rows sorted by timestamp."""
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["temp_c"]       = float(r["temp_c"])
        r["wind_speed_ms"] = float(r["wind_speed_ms"])
        r["is_forecast"]   = int(r["is_forecast"])
    return sorted(rows, key=lambda r: r["timestamp"])


def load_consumption(meter_id: int,
                     path: str = "data/consumption.csv") -> list[dict]:
    """
    Return half-hourly gas kWh rows for one meter, sorted by timestamp.
    Filters out readings above GAS_CAP_M3 (sentinel / error values).
    """
    mpxn = METERS[meter_id]
    rows = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            if row["mpxn"] != mpxn or row["utility"] != "gas":
                continue
            val_m3 = float(row["value"])
            if val_m3 > GAS_CAP_M3:
                continue
            rows.append({
                "timestamp": row["timestamp"],
                "gas_kwh":   round(val_m3 * GAS_KWH_PER_M3, 4),
            })
    return sorted(rows, key=lambda r: r["timestamp"])


def build_daily_gas_hdd(meter_id: int,
                         start: str,
                         end: str) -> list[dict]:
    """
    Aggregate half-hourly gas and weather to daily records between start and end (inclusive).
    Returns list of {"date": str, "hdd": float, "gas_kwh": float, "mean_temp_c": float}.
    Only includes days with >=40 gas readings and >=40 weather readings (guard against gaps).
    """
    weather = {r["timestamp"][:10]: [] for r in load_weather()
               if start <= r["timestamp"][:10] <= end}
    for r in load_weather():
        d = r["timestamp"][:10]
        if start <= d <= end:
            weather.setdefault(d, []).append(r["temp_c"])

    gas: dict[str, float] = {}
    gas_count: dict[str, int] = {}
    for r in load_consumption(meter_id):
        d = r["timestamp"][:10]
        if start <= d <= end:
            gas[d] = gas.get(d, 0.0) + r["gas_kwh"]
            gas_count[d] = gas_count.get(d, 0) + 1

    result = []
    for d in sorted(weather):
        temps = weather[d]
        if len(temps) < 40 or gas_count.get(d, 0) < 40:
            continue
        mean_temp = sum(temps) / len(temps)
        hdd       = daily_hdd(mean_temp)
        result.append({
            "date":       d,
            "hdd":        round(hdd, 3),
            "gas_kwh":    round(gas.get(d, 0.0), 4),
            "mean_temp_c": round(mean_temp, 2),
        })
    return result
```

- [ ] **Step 4: Run tests**

```bash
cd /c/Users/steve/projects/smart_meter
python -m pytest tests/test_tier2_lib.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add py/tier2_lib.py tests/test_tier2_lib.py
git commit -m "feat: add tier2_lib.py shared HDD regression foundation with tests"
```

---

## Task 3: s06_heating_efficiency.py — Heating Efficiency Scoring

**Files:**
- Create: `py/s06_heating_efficiency.py`
- Create: `tests/test_s06_heating_efficiency.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_s06_heating_efficiency.py`:

```python
import pytest
from s06_heating_efficiency import (
    daily_efficiency_score,
    flag_anomalous_days,
)


# --- daily_efficiency_score ---

def test_score_exactly_as_expected():
    result = daily_efficiency_score(
        actual_gas_kwh=50.0, hdd=5.0,
        slope=8.0, intercept=10.0, slope_std=3.0,
    )
    # expected = 8*5 + 10 = 50
    assert result["score"] == pytest.approx(100.0)
    assert result["z_score"] == pytest.approx(0.0)
    assert result["anomalous"] is False

def test_score_over_consuming():
    result = daily_efficiency_score(
        actual_gas_kwh=70.0, hdd=5.0,
        slope=8.0, intercept=10.0, slope_std=4.0,
    )
    # expected=50, residual=20, z=20/4=5.0
    assert result["score"] == pytest.approx(140.0)
    assert result["z_score"] == pytest.approx(5.0)
    assert result["anomalous"] is True
    assert result["anomaly_type"] == "over_consuming"

def test_score_mild_day_returns_none():
    result = daily_efficiency_score(
        actual_gas_kwh=5.0, hdd=0.3,
        slope=8.0, intercept=10.0, slope_std=3.0,
    )
    assert result["score"] is None
    assert result["reason"] == "too_mild"


# --- flag_anomalous_days ---

def _make_scores(anomalous_flags: list[bool]) -> list[dict]:
    return [
        {"anomalous": a, "score": 120.0 if a else 100.0,
         "anomaly_type": "over_consuming" if a else None}
        for a in anomalous_flags
    ]

def test_flag_three_consecutive():
    scores = _make_scores([False, True, True, True, False])
    winds  = [3.0, 3.0, 3.0, 3.0, 3.0]
    result = flag_anomalous_days(scores, winds)
    assert result[1]["sustained_alert"] is True
    assert result[2]["sustained_alert"] is True
    assert result[3]["sustained_alert"] is True
    assert result[0]["sustained_alert"] is False

def test_flag_suppressed_by_wind():
    scores = _make_scores([True, True, True])
    winds  = [9.0, 9.0, 9.0]   # all above 8 m/s
    result = flag_anomalous_days(scores, winds)
    assert all(not r["sustained_alert"] for r in result)

def test_flag_two_consecutive_not_enough():
    scores = _make_scores([True, True, False, False])
    winds  = [3.0, 3.0, 3.0, 3.0]
    result = flag_anomalous_days(scores, winds)
    assert all(not r["sustained_alert"] for r in result)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /c/Users/steve/projects/smart_meter
python -m pytest tests/test_s06_heating_efficiency.py -v 2>&1 | head -10
```

Expected: `ImportError: No module named 's06_heating_efficiency'`

- [ ] **Step 3: Create py/s06_heating_efficiency.py**

```python
"""
Service #6 — Heating Efficiency Scoring.

For each meter, fits an HDD regression (heating season days HDD > 0.5,
R² >= 0.60 required) and scores every heating day in WINTER_START–WINTER_END.
Flags sustained anomalous days (z > 2.5 for 3+ consecutive days, wind < 8 m/s).
Benchmarks each meter against UK peer properties.

Run: python py/s06_heating_efficiency.py
Outputs: data/s06_heating_efficiency.csv
"""

import csv
import math
from datetime import date

from config import (
    GAS_RATE_P_KWH,
    METERS,
    METER_META,
    REGRESSION_START,
    REGRESSION_END,
    WINTER_START,
    WINTER_END,
)
from tier2_lib import (
    build_daily_gas_hdd,
    fit_hdd_regression,
    benchmark_percentile,
    load_weather,
)

OUT_FILE = "data/s06_heating_efficiency.csv"
MIN_R2   = 0.60
Z_ALERT  = 2.5
WIND_SUPPRESS_MS = 8.0
CONSECUTIVE_MIN  = 3


def daily_efficiency_score(actual_gas_kwh: float,
                            hdd: float,
                            slope: float,
                            intercept: float,
                            slope_std: float) -> dict:
    if hdd < 0.5:
        return {"score": None, "reason": "too_mild"}
    expected_kwh = slope * hdd + intercept
    residual_kwh = actual_gas_kwh - expected_kwh
    z_score      = residual_kwh / max(slope_std, 1.0)
    score        = round(100 * actual_gas_kwh / expected_kwh, 1) if expected_kwh > 0 else None
    anomalous    = abs(z_score) > Z_ALERT
    anomaly_type = None
    if anomalous:
        anomaly_type = "over_consuming" if z_score > 0 else "under_consuming"
    return {
        "score":        score,
        "expected_kwh": round(expected_kwh, 2),
        "actual_kwh":   round(actual_gas_kwh, 2),
        "residual_kwh": round(residual_kwh, 2),
        "z_score":      round(z_score, 2),
        "anomalous":    anomalous,
        "anomaly_type": anomaly_type,
    }


def flag_anomalous_days(daily_scores: list[dict],
                         daily_wind_ms: list[float]) -> list[dict]:
    """
    Mark sustained_alert=True on days where z > Z_ALERT for 3+ consecutive days
    and wind < WIND_SUPPRESS_MS.
    """
    n = len(daily_scores)
    result = [dict(s, sustained_alert=False) for s in daily_scores]

    for i in range(n - CONSECUTIVE_MIN + 1):
        window = [(daily_scores[i + j], daily_wind_ms[i + j])
                  for j in range(CONSECUTIVE_MIN)]
        if all(s.get("anomalous") and w < WIND_SUPPRESS_MS
               for s, w in window):
            for j in range(CONSECUTIVE_MIN):
                result[i + j]["sustained_alert"] = True

    return result


def _residual_std(records: list[tuple[float, float]],
                   slope: float,
                   intercept: float) -> float:
    residuals = [g - (slope * h + intercept) for h, g in records]
    n = len(residuals)
    if n < 2:
        return 1.0
    mean_r = sum(residuals) / n
    return math.sqrt(sum((r - mean_r) ** 2 for r in residuals) / (n - 1))


def analyse_meter(meter_id: int) -> list[dict]:
    meta = METER_META[meter_id]

    regression_days = build_daily_gas_hdd(meter_id, REGRESSION_START, REGRESSION_END)
    heating_days    = [(d["hdd"], d["gas_kwh"]) for d in regression_days if d["hdd"] > 0.5]

    if len(heating_days) < 60:
        print(f"  M{meter_id}: insufficient heating days ({len(heating_days)}) — skipping")
        return []

    slope, intercept, r_sq = fit_hdd_regression(heating_days)
    if r_sq < MIN_R2:
        print(f"  M{meter_id}: R²={r_sq:.2f} < {MIN_R2} — regression too weak, skipping")
        return []

    slope_std = _residual_std(heating_days, slope, intercept)

    winter_days = build_daily_gas_hdd(meter_id, WINTER_START, WINTER_END)
    weather_map = {r["timestamp"][:10]: float(r["wind_speed_ms"])
                   for r in load_weather()}

    scored = []
    for d in winter_days:
        s = daily_efficiency_score(d["gas_kwh"], d["hdd"], slope, intercept, slope_std)
        s["date"]    = d["date"]
        s["hdd"]     = d["hdd"]
        s["wind_ms"] = weather_map.get(d["date"], 0.0)
        scored.append(s)

    winds  = [s["wind_ms"] for s in scored]
    scored = flag_anomalous_days(scored, winds)

    heating_scored = [s for s in scored if s["score"] is not None]
    total_hdd  = sum(d["hdd"] for d in winter_days if d["hdd"] > 0)
    total_gas  = sum(d["gas_kwh"] for d in winter_days)
    kwh_per_hdd = total_gas / total_hdd if total_hdd > 0 else 0.0
    bench = benchmark_percentile(kwh_per_hdd, meta["property_type"], meta["build_era"])

    mean_score   = sum(s["score"] for s in heating_scored) / max(len(heating_scored), 1)
    alert_count  = sum(1 for s in scored if s.get("sustained_alert"))

    print(f"  M{meter_id}: R²={r_sq:.2f}  mean_score={mean_score:.0f}  "
          f"alert_days={alert_count}  "
          f"benchmark={bench['band']} ({bench.get('percentile', '-')}th pct)")

    rows = []
    for s in scored:
        rows.append({
            "meter_id":    meter_id,
            "date":        s["date"],
            "hdd":         s["hdd"],
            "expected_kwh": s.get("expected_kwh", ""),
            "actual_kwh":  s.get("actual_kwh", ""),
            "score":       s.get("score", ""),
            "z_score":     s.get("z_score", ""),
            "anomalous":   s.get("anomalous", ""),
            "anomaly_type": s.get("anomaly_type", ""),
            "sustained_alert": s.get("sustained_alert", ""),
        })
    return rows


def main():
    print("Service #6 — Heating Efficiency Scoring")
    print(f"  Regression window: {REGRESSION_START} to {REGRESSION_END}")
    print(f"  Scoring window:    {WINTER_START} to {WINTER_END}\n")

    all_rows = []
    for meter_id in sorted(METERS):
        all_rows.extend(analyse_meter(meter_id))

    fields = ["meter_id", "date", "hdd", "expected_kwh", "actual_kwh",
              "score", "z_score", "anomalous", "anomaly_type", "sustained_alert"]
    with open(OUT_FILE, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(all_rows)

    print(f"\nWrote {len(all_rows)} rows to {OUT_FILE}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests**

```bash
cd /c/Users/steve/projects/smart_meter
python -m pytest tests/test_s06_heating_efficiency.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Smoke-test the script**

```bash
python py/s06_heating_efficiency.py
```

Expected: per-meter summary printed, `data/s06_heating_efficiency.csv` written.

- [ ] **Step 6: Commit**

```bash
git add py/s06_heating_efficiency.py tests/test_s06_heating_efficiency.py
git commit -m "feat: add s06_heating_efficiency — daily HDD efficiency scoring with peer benchmark"
```

---

## Task 4: s05_boiler_trending.py — Boiler Efficiency Trending

**Files:**
- Create: `py/s05_boiler_trending.py`
- Create: `tests/test_s05_boiler_trending.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_s05_boiler_trending.py`:

```python
import pytest
from s05_boiler_trending import classify_trend, detect_boiler_degradation


# --- classify_trend ---

def test_classify_trend_stable():
    weekly = [10.0, 10.1, 9.9, 10.0, 10.1, 9.8, 10.0, 10.2]
    assert classify_trend(weekly) == "stable"

def test_classify_trend_gradual():
    # Steadily rising: 10, 10.2, 10.4, ... +0.2/week for 8 weeks → slope ≈ 0.2
    weekly = [10.0 + i * 0.2 for i in range(8)]
    assert classify_trend(weekly) == "gradual_trend"

def test_classify_trend_step_change():
    # Flat then jump
    weekly = [10.0, 10.0, 10.0, 10.0, 12.5, 12.5, 12.5, 12.5]
    assert classify_trend(weekly) == "step_change"

def test_classify_trend_insufficient():
    assert classify_trend([10.0, 11.0]) == "insufficient_data"


# --- detect_boiler_degradation ---

def _make_records(kwh_per_hdd: float, n: int = 30) -> list[tuple[float, float]]:
    return [(5.0, 5.0 * kwh_per_hdd) for _ in range(n)]

def test_detect_no_alert():
    baseline = _make_records(10.0, 60)
    recent   = _make_records(10.5, 20)   # 5% rise — below 15% threshold
    result   = detect_boiler_degradation(baseline, recent)
    assert result["alert"] is False
    assert result["pct_change"] == pytest.approx(5.0, abs=0.1)

def test_detect_medium_alert():
    baseline = _make_records(10.0, 60)
    recent   = _make_records(11.8, 20)   # 18% rise
    result   = detect_boiler_degradation(baseline, recent)
    assert result["alert"] is True
    assert result["alert_severity"] == "MEDIUM"

def test_detect_high_alert():
    baseline = _make_records(10.0, 60)
    recent   = _make_records(13.0, 20)   # 30% rise
    result   = detect_boiler_degradation(baseline, recent)
    assert result["alert"] is True
    assert result["alert_severity"] == "HIGH"

def test_detect_insufficient_baseline():
    baseline = _make_records(10.0, 10)   # < 60 days
    recent   = _make_records(12.0, 20)
    result   = detect_boiler_degradation(baseline, recent)
    assert result["status"] == "insufficient_data"

def test_detect_insufficient_recent():
    baseline = _make_records(10.0, 60)
    recent   = _make_records(12.0, 5)    # < 20 days
    result   = detect_boiler_degradation(baseline, recent)
    assert result["status"] == "insufficient_data"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_s05_boiler_trending.py -v 2>&1 | head -10
```

Expected: `ImportError`

- [ ] **Step 3: Create py/s05_boiler_trending.py**

```python
"""
Service #5 — Boiler Efficiency Trending.

Compares baseline heating season kWh/HDD against the past 28 days.
Alerts if recent efficiency is >15% worse than baseline.

Run: python py/s05_boiler_trending.py
Outputs: data/s05_boiler_trending.csv
"""

import csv
from datetime import date, timedelta

from config import METERS, REGRESSION_START, REGRESSION_END
from tier2_lib import build_daily_gas_hdd

OUT_FILE               = "data/s05_boiler_trending.csv"
TREND_ALERT_THRESHOLD  = 0.15
TREND_HIGH_THRESHOLD   = 0.25
MIN_BASELINE_HDD_DAYS  = 60
MIN_RECENT_HDD_DAYS    = 20


def classify_trend(weekly_kwh_per_hdd: list[float]) -> str:
    n = len(weekly_kwh_per_hdd)
    if n < 8:
        return "insufficient_data"
    x_mean = (n - 1) / 2.0
    y_mean = sum(weekly_kwh_per_hdd) / n
    num    = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(weekly_kwh_per_hdd))
    den    = sum((i - x_mean) ** 2 for i in range(n))
    slope  = num / den if den > 0 else 0.0
    first  = weekly_kwh_per_hdd[:n // 2]
    second = weekly_kwh_per_hdd[n // 2:]
    step_ratio = (sum(second) / len(second)) / (sum(first) / len(first))
    if step_ratio > 1.20 and slope < 0.01:
        return "step_change"
    if slope > 0.008:
        return "gradual_trend"
    return "stable"


def detect_boiler_degradation(baseline_records: list[tuple[float, float]],
                               recent_records:   list[tuple[float, float]]) -> dict:
    if (len(baseline_records) < MIN_BASELINE_HDD_DAYS or
            len(recent_records) < MIN_RECENT_HDD_DAYS):
        return {"status": "insufficient_data"}
    base_kwh_per_hdd   = (sum(g for _, g in baseline_records) /
                           sum(h for h, _ in baseline_records))
    recent_kwh_per_hdd = (sum(g for _, g in recent_records) /
                           sum(h for h, _ in recent_records))
    pct = (recent_kwh_per_hdd - base_kwh_per_hdd) / base_kwh_per_hdd * 100
    alert    = pct > TREND_ALERT_THRESHOLD * 100
    severity = ("HIGH"   if pct > TREND_HIGH_THRESHOLD * 100 else
                "MEDIUM" if alert else None)
    return {
        "status":               "ok",
        "baseline_kwh_per_hdd": round(base_kwh_per_hdd, 2),
        "recent_kwh_per_hdd":   round(recent_kwh_per_hdd, 2),
        "pct_change":           round(pct, 1),
        "alert":                alert,
        "alert_severity":       severity,
    }


def _weekly_series(heating_days: list[dict]) -> list[float]:
    """Group HDD-days into 4-week bins and return kWh/HDD per bin."""
    if not heating_days:
        return []
    from_d = date.fromisoformat(heating_days[0]["date"])
    bins: dict[int, list[tuple[float, float]]] = {}
    for d in heating_days:
        week = (date.fromisoformat(d["date"]) - from_d).days // 7
        bins.setdefault(week, []).append((d["hdd"], d["gas_kwh"]))
    result = []
    for w in sorted(bins):
        pairs = bins[w]
        total_hdd = sum(h for h, _ in pairs)
        total_gas = sum(g for _, g in pairs)
        if total_hdd > 0:
            result.append(total_gas / total_hdd)
    return result


def analyse_meter(meter_id: int) -> dict:
    all_days = build_daily_gas_hdd(meter_id, REGRESSION_START, REGRESSION_END)
    heating  = [d for d in all_days if d["hdd"] > 0.5]

    today     = date.today()
    cutoff    = (today - timedelta(days=28)).isoformat()
    baseline  = [(d["hdd"], d["gas_kwh"]) for d in heating
                 if d["date"] < cutoff]
    recent    = [(d["hdd"], d["gas_kwh"]) for d in heating
                 if d["date"] >= cutoff]

    result  = detect_boiler_degradation(baseline, recent)
    weekly  = _weekly_series([d for d in heating if d["date"] < cutoff])
    trend   = classify_trend(weekly)

    result["meter_id"]   = meter_id
    result["trend_type"] = trend

    if result.get("status") == "insufficient_data":
        print(f"  M{meter_id}: insufficient data")
    else:
        alert_str = f"ALERT ({result['alert_severity']})" if result["alert"] else "ok"
        print(f"  M{meter_id}: baseline={result['baseline_kwh_per_hdd']} "
              f"recent={result['recent_kwh_per_hdd']} "
              f"change={result['pct_change']:+.1f}%  {alert_str}  [{trend}]")
    return result


def main():
    print("Service #5 — Boiler Efficiency Trending\n")
    fields = ["meter_id", "baseline_kwh_per_hdd", "recent_kwh_per_hdd",
              "pct_change", "alert", "alert_severity", "trend_type", "status"]
    rows = []
    for meter_id in sorted(METERS):
        r = analyse_meter(meter_id)
        rows.append({f: r.get(f, "") for f in fields})

    with open(OUT_FILE, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"\nWrote {len(rows)} rows to {OUT_FILE}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_s05_boiler_trending.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Smoke-test**

```bash
python py/s05_boiler_trending.py
```

Expected: per-meter summary + `data/s05_boiler_trending.csv` written.

- [ ] **Step 6: Commit**

```bash
git add py/s05_boiler_trending.py tests/test_s05_boiler_trending.py
git commit -m "feat: add s05_boiler_trending — normalised efficiency degradation detection"
```

---

## Task 5: s07_budget_forecast.py — Degree-Day Budget Forecasting

**Files:**
- Create: `py/s07_budget_forecast.py`
- Create: `tests/test_s07_budget_forecast.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_s07_budget_forecast.py`:

```python
import pytest
from datetime import date
from s07_budget_forecast import (
    compute_monthly_budget,
    thermostat_nudge,
    project_kwh_for_day,
)


# --- compute_monthly_budget ---

def test_monthly_budget_mean_of_twelve():
    # 12 months at £50 each → budget = £50
    monthly = [50.0] * 12
    assert compute_monthly_budget(monthly) == pytest.approx(50.0)

def test_monthly_budget_varying():
    monthly = [40.0, 60.0, 50.0, 80.0, 20.0, 30.0,
               10.0, 10.0, 20.0, 50.0, 70.0, 60.0]
    assert compute_monthly_budget(monthly) == pytest.approx(sum(monthly) / 12)

def test_monthly_budget_fewer_than_12_still_averages():
    monthly = [60.0, 40.0]
    assert compute_monthly_budget(monthly) == pytest.approx(50.0)


# --- project_kwh_for_day ---

def test_project_kwh_heating_day():
    # slope=8, intercept=5, hdd=5 → expected=45
    assert project_kwh_for_day(5.0, 8.0, 5.0) == pytest.approx(45.0)

def test_project_kwh_warm_day():
    assert project_kwh_for_day(0.0, 8.0, 5.0) == pytest.approx(5.0)


# --- thermostat_nudge ---

def test_nudge_calculates_reduction():
    # gap=£10, rate=6p/kWh → gap_kwh = 10*100/6 = 166.7 kWh
    # slope=8 kWh/HDD, 10 remaining days
    # reduction = 166.7 / (8 * 10) = 2.08°C
    result = thermostat_nudge(
        budget_gap_gbp=10.0,
        remaining_days=10,
        gas_rate_p_per_kwh=6.0,
        slope=8.0,
    )
    assert result["thermostat_reduction_c"] == pytest.approx(2.1, abs=0.1)
    assert result["budget_gap_kwh"] == pytest.approx(166.7, abs=0.5)

def test_nudge_zero_days():
    result = thermostat_nudge(10.0, 0, 6.0, 8.0)
    assert result == {}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_s07_budget_forecast.py -v 2>&1 | head -10
```

Expected: `ImportError`

- [ ] **Step 3: Create py/s07_budget_forecast.py**

```python
"""
Service #7 — Degree-Day Budget Forecasting.

Auto-computes a monthly gas budget from the past 12 months' average spend,
then projects the current month's remaining spend using forecast temperatures.

Run: python py/s07_budget_forecast.py
Outputs: data/s07_budget_forecast.csv
"""

import csv
import calendar
from datetime import date, timedelta

from config import GAS_RATE_P_KWH, METERS, REGRESSION_START, REGRESSION_END
from tier2_lib import (
    build_daily_gas_hdd,
    fit_hdd_regression,
    load_weather,
    daily_hdd,
)

OUT_FILE = "data/s07_budget_forecast.csv"

CLIMATOLOGICAL_MEAN_C = {
    1: 4.2, 2: 4.5, 3: 6.5, 4: 9.0, 5: 12.0, 6: 15.0,
    7: 17.0, 8: 16.8, 9: 14.0, 10: 10.5, 11: 7.0, 12: 4.8,
}
FORECAST_UNCERTAINTY_C = 2.0   # fixed 1σ uncertainty for remaining days


def compute_monthly_budget(monthly_spend_gbp: list[float]) -> float:
    return sum(monthly_spend_gbp) / len(monthly_spend_gbp)


def project_kwh_for_day(hdd: float, slope: float, intercept: float) -> float:
    return slope * hdd + intercept


def thermostat_nudge(budget_gap_gbp: float,
                      remaining_days: int,
                      gas_rate_p_per_kwh: float,
                      slope: float) -> dict:
    if remaining_days == 0 or slope == 0:
        return {}
    gap_kwh = budget_gap_gbp * 100 / gas_rate_p_per_kwh
    reduction = gap_kwh / (slope * remaining_days)
    return {
        "thermostat_reduction_c": round(reduction, 1),
        "budget_gap_kwh":         round(gap_kwh, 1),
        "days_to_implement_by":   remaining_days,
    }


def _monthly_spend(all_days: list[dict]) -> dict[str, float]:
    """Sum gas spend (£) per calendar month from daily records."""
    monthly: dict[str, float] = {}
    for d in all_days:
        month_key = d["date"][:7]   # "YYYY-MM"
        spend = d["gas_kwh"] * GAS_RATE_P_KWH / 100
        monthly[month_key] = monthly.get(month_key, 0.0) + spend
    return monthly


def _forecast_temp_map() -> dict[str, tuple[float, float]]:
    """Return {date_str: (mean_temp_c, uncertainty_c)} for forecast days."""
    result = {}
    for r in load_weather():
        if r["is_forecast"] == 1:
            d = r["timestamp"][:10]
            result.setdefault(d, []).append(r["temp_c"])
    return {d: (sum(v) / len(v), FORECAST_UNCERTAINTY_C) for d, v in result.items()}


def analyse_meter(meter_id: int) -> dict:
    today = date.today()

    all_days = build_daily_gas_hdd(meter_id, REGRESSION_START, REGRESSION_END)

    # 12-month budget
    monthly_spend = _monthly_spend(all_days)
    twelve_months = sorted(monthly_spend)[-12:]
    if not twelve_months:
        print(f"  M{meter_id}: no monthly data")
        return {"meter_id": meter_id, "status": "insufficient_data"}
    budget = compute_monthly_budget([monthly_spend[m] for m in twelve_months])

    # Regression for projection
    heating_days = [(d["hdd"], d["gas_kwh"]) for d in all_days if d["hdd"] > 0.5]
    slope, intercept, r_sq = fit_hdd_regression(heating_days)

    # Actual spend this month so far
    month_start = today.replace(day=1).isoformat()
    actual_so_far_kwh = sum(
        d["gas_kwh"] for d in all_days
        if month_start <= d["date"] <= today.isoformat()
    )
    actual_so_far_gbp = actual_so_far_kwh * GAS_RATE_P_KWH / 100

    # Remaining days
    days_in_month  = calendar.monthrange(today.year, today.month)[1]
    remaining_days = [
        today + timedelta(days=i)
        for i in range(1, days_in_month - today.day + 1)
    ]

    forecast_map = _forecast_temp_map()

    proj_central = proj_high = proj_low = 0.0
    for d in remaining_days:
        ds = d.isoformat()
        if ds in forecast_map:
            mean_t, std = forecast_map[ds]
        else:
            mean_t = CLIMATOLOGICAL_MEAN_C[d.month]
            std    = FORECAST_UNCERTAINTY_C
        hdd_c    = daily_hdd(mean_t)
        hdd_cold = daily_hdd(mean_t - std)
        hdd_warm = daily_hdd(mean_t + std)
        proj_central += project_kwh_for_day(hdd_c,    slope, intercept)
        proj_high    += project_kwh_for_day(hdd_cold, slope, intercept)
        proj_low     += project_kwh_for_day(hdd_warm, slope, intercept)

    total_c = actual_so_far_gbp + proj_central * GAS_RATE_P_KWH / 100
    total_h = actual_so_far_gbp + proj_high    * GAS_RATE_P_KWH / 100
    total_l = actual_so_far_gbp + proj_low     * GAS_RATE_P_KWH / 100
    gap     = total_c - budget
    exceed  = total_h > budget

    nudge = {}
    if exceed:
        nudge = thermostat_nudge(max(gap, 0), len(remaining_days),
                                  GAS_RATE_P_KWH, slope)

    print(f"  M{meter_id}: budget=£{budget:.2f}  "
          f"actual=£{actual_so_far_gbp:.2f}  "
          f"proj=£{total_c:.2f} [£{total_l:.2f}–£{total_h:.2f}]  "
          f"gap={gap:+.2f}  exceed={exceed}"
          + (f"  nudge={nudge['thermostat_reduction_c']}°C" if nudge else ""))

    return {
        "meter_id":            meter_id,
        "monthly_budget_gbp":  round(budget, 2),
        "actual_so_far_gbp":   round(actual_so_far_gbp, 2),
        "projected_total_gbp": round(total_c, 2),
        "projected_high_gbp":  round(total_h, 2),
        "projected_low_gbp":   round(total_l, 2),
        "budget_gap_gbp":      round(gap, 2),
        "will_exceed":         exceed,
        "thermostat_reduction_c": nudge.get("thermostat_reduction_c", ""),
        "days_remaining":      len(remaining_days),
        "status":              "ok",
    }


def main():
    print("Service #7 — Degree-Day Budget Forecasting\n")
    fields = ["meter_id", "monthly_budget_gbp", "actual_so_far_gbp",
              "projected_total_gbp", "projected_high_gbp", "projected_low_gbp",
              "budget_gap_gbp", "will_exceed", "thermostat_reduction_c",
              "days_remaining", "status"]
    rows = []
    for meter_id in sorted(METERS):
        rows.append(analyse_meter(meter_id))

    with open(OUT_FILE, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows([{f: r.get(f, "") for f in fields} for r in rows])
    print(f"\nWrote {len(rows)} rows to {OUT_FILE}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_s07_budget_forecast.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Smoke-test**

```bash
python py/s07_budget_forecast.py
```

Expected: per-meter budget summary + `data/s07_budget_forecast.csv` written.

- [ ] **Step 6: Commit**

```bash
git add py/s07_budget_forecast.py tests/test_s07_budget_forecast.py
git commit -m "feat: add s07_budget_forecast — monthly gas spend projection with thermostat nudge"
```

---

## Task 6: s10_leak_frost.py — Micro-Leak and Frost Detection

**Files:**
- Create: `py/s10_leak_frost.py`
- Create: `tests/test_s10_leak_frost.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_s10_leak_frost.py`:

```python
import pytest
from s10_leak_frost import (
    overnight_baseline_kwh,
    detect_gas_leak,
    frost_alert,
    heating_failure_frost_alert,
)


# --- overnight_baseline_kwh ---

def _make_readings(vals: list[float], month: int = 6) -> list[tuple]:
    from datetime import date
    return [(date(2025, month, 1), p, v) for p, v in enumerate(vals)]

def test_baseline_computes_median():
    readings = _make_readings([0.01] * 10 + [0.05] * 10 + [0.10] * 10)
    result = overnight_baseline_kwh(readings)
    assert result["median_kwh"] == pytest.approx(0.05)

def test_baseline_insufficient_data():
    readings = _make_readings([0.01] * 5)
    result = overnight_baseline_kwh(readings)
    assert result["status"] == "insufficient_data"


# --- detect_gas_leak ---

def _baseline(median=0.01):
    return {"median_kwh": median, "p95_kwh": 0.05, "p99_kwh": 0.08}

def test_no_leak_all_below_threshold():
    readings = [0.02] * 10   # 2× median < 3× → no alert
    result = detect_gas_leak(readings, _baseline(0.01))
    assert result["alert"] is False

def test_leak_six_consecutive():
    readings = [0.00, 0.04, 0.04, 0.04, 0.04, 0.04, 0.04, 0.00]
    # threshold = max(3*0.01, 0.05) = 0.05; readings of 0.04 < 0.05 → no
    # Try with median=0.005 so threshold=0.05 and 0.04 < threshold still
    # Use higher values:
    readings = [0.00, 0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.00]
    result = detect_gas_leak(readings, _baseline(0.01))
    assert result["alert"] is True
    assert result["max_consecutive_periods"] == 6

def test_leak_alert_requires_six_consecutive():
    # Only 5 consecutive above threshold
    readings = [0.10, 0.10, 0.10, 0.10, 0.10, 0.00, 0.10]
    result = detect_gas_leak(readings, _baseline(0.01))
    assert result["alert"] is False


# --- frost_alert ---

def test_frost_no_alert_warm():
    result = frost_alert([0.0] * 12, 5.0, 4)
    assert result["alert"] is False

def test_frost_alert_vacant_high():
    result = frost_alert([0.0] * 12, 1.0, 4)
    assert result["alert"] is True
    assert result["severity"] == "HIGH"

def test_frost_alert_vacant_critical():
    result = frost_alert([0.0] * 12, -4.0, 4)
    assert result["alert"] is True
    assert result["severity"] == "CRITICAL"

def test_frost_no_alert_occupied():
    # Recent gas > 0.05 → not vacant → no alert
    result = frost_alert([0.1] * 12, -4.0, 4)
    assert result["alert"] is False


# --- heating_failure_frost_alert ---

def test_heating_failure_alert():
    result = heating_failure_frost_alert(
        expected_heating=True, actual_gas_kwh=0.05,
        outdoor_temp_c=3.0, forecast_low_c=1.0,
    )
    assert result["alert"] is True
    assert result["alert_type"] == "heating_failure_with_frost_risk"

def test_heating_failure_no_alert_boiler_running():
    result = heating_failure_frost_alert(
        expected_heating=True, actual_gas_kwh=0.5,
        outdoor_temp_c=3.0, forecast_low_c=1.0,
    )
    assert result["alert"] is False

def test_heating_failure_no_alert_warm_forecast():
    result = heating_failure_frost_alert(
        expected_heating=True, actual_gas_kwh=0.05,
        outdoor_temp_c=3.0, forecast_low_c=5.0,
    )
    assert result["alert"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_s10_leak_frost.py -v 2>&1 | head -10
```

Expected: `ImportError`

- [ ] **Step 3: Create py/s10_leak_frost.py**

```python
"""
Service #10 — Micro-Leak and Frost Detection.

Micro-leak: flags sustained above-baseline overnight gas consumption.
Frost: alerts when property appears vacant and sub-zero temps are forecast,
       or when boiler appears off during expected heating with frost incoming.

Run: python py/s10_leak_frost.py
Outputs: data/s10_leak_frost.csv
"""

import csv
from datetime import date, datetime, timedelta

from config import METERS
from tier2_lib import load_consumption, load_weather, daily_hdd

OUT_FILE = "data/s10_leak_frost.csv"

OVERNIGHT_PERIODS   = list(range(0, 8)) + list(range(44, 48))
SUMMER_MONTHS       = {5, 6, 7, 8, 9}
LEAK_MIN_SAMPLES    = 30
LEAK_THRESHOLD_MULT = 3.0
LEAK_ABS_MIN_KWH    = 0.05
LEAK_SUSTAINED      = 6
FROST_RISK_C        = 2.0
PIPE_BURST_C        = -3.0
VACANT_HOURS        = 12
BOILER_ON_KWH       = 0.15


def overnight_baseline_kwh(readings: list[tuple]) -> dict:
    """
    readings: list of (date, period_index, gas_kwh)
    Computes statistics from summer overnight periods.
    """
    vals = [kwh for d, p, kwh in readings
            if d.month in SUMMER_MONTHS and p in OVERNIGHT_PERIODS and kwh is not None]
    if len(vals) < LEAK_MIN_SAMPLES:
        return {"status": "insufficient_data"}
    vals.sort()
    n = len(vals)
    return {
        "median_kwh":   vals[n // 2],
        "p95_kwh":      vals[int(n * 0.95)],
        "p99_kwh":      vals[int(n * 0.99)],
        "sample_count": n,
    }


def detect_gas_leak(overnight_readings: list[float], baseline: dict) -> dict:
    threshold = max(baseline["median_kwh"] * LEAK_THRESHOLD_MULT, LEAK_ABS_MIN_KWH)
    above     = [v >= threshold for v in overnight_readings]
    consec = max_consec = 0
    for flag in above:
        consec = consec + 1 if flag else 0
        max_consec = max(max_consec, consec)
    alert     = max_consec >= LEAK_SUSTAINED
    above_vals = [v for v in overnight_readings if v >= threshold]
    mean_excess = ((sum(v - baseline["median_kwh"] for v in above_vals) / len(above_vals))
                   if above_vals else 0.0)
    return {
        "alert":                   alert,
        "max_consecutive_periods": max_consec,
        "threshold_kwh":           round(threshold, 4),
        "mean_excess_kwh":         round(mean_excess, 4),
        "annualised_waste_kwh":    round(mean_excess * len(OVERNIGHT_PERIODS) * 365, 0) if alert else 0,
    }


def frost_alert(recent_gas_kwh: list[float],
                 overnight_forecast_low_c: float,
                 forecast_min_period: int) -> dict:
    if overnight_forecast_low_c >= FROST_RISK_C:
        return {"alert": False}
    vacant = all(g < 0.05 for g in recent_gas_kwh)
    if not vacant:
        return {"alert": False, "reason": "heating_has_been_active"}
    severity = "CRITICAL" if overnight_forecast_low_c < PIPE_BURST_C else "HIGH"
    return {
        "alert":               True,
        "severity":            severity,
        "forecast_low_c":      round(overnight_forecast_low_c, 1),
        "forecast_min_period": forecast_min_period,
        "action": "Set heating to minimum 10°C or ask neighbour to check property.",
    }


def heating_failure_frost_alert(expected_heating: bool,
                                  actual_gas_kwh: float,
                                  outdoor_temp_c: float,
                                  forecast_low_c: float) -> dict:
    boiler_absent = actual_gas_kwh < BOILER_ON_KWH
    if not (expected_heating and boiler_absent and forecast_low_c < FROST_RISK_C):
        return {"alert": False}
    return {
        "alert":          True,
        "severity":       "HIGH",
        "alert_type":     "heating_failure_with_frost_risk",
        "outdoor_temp_c": round(outdoor_temp_c, 1),
        "forecast_low_c": round(forecast_low_c, 1),
        "action":         "Boiler appears off. Check boiler pressure and power before overnight frost.",
    }


def _to_readings(consumption_rows: list[dict]) -> list[tuple]:
    result = []
    for r in consumption_rows:
        ts = datetime.strptime(r["timestamp"], "%Y-%m-%d %H:%M")
        period = ts.hour * 2 + ts.minute // 30
        result.append((ts.date(), period, r["gas_kwh"]))
    return result


def _recent_hourly_gas(consumption_rows: list[dict], hours: int = 12) -> list[float]:
    """Return hourly gas totals for the past `hours` hours."""
    now   = datetime.now()
    cutoff = now - timedelta(hours=hours)
    by_hour: dict[int, float] = {}
    for r in consumption_rows:
        ts = datetime.strptime(r["timestamp"], "%Y-%m-%d %H:%M")
        if ts >= cutoff:
            h = ts.hour
            by_hour[h] = by_hour.get(h, 0.0) + r["gas_kwh"]
    return [by_hour.get(h, 0.0) for h in range(hours)]


def _forecast_overnight_low(weather_rows: list[dict]) -> tuple[float, int]:
    """Return (min_forecast_temp, period_index) for the next 24h of forecast data."""
    tonight = [r for r in weather_rows
               if r["is_forecast"] == 1
               and int(r["timestamp"][11:13]) < 6]
    if not tonight:
        return 10.0, 0
    coldest = min(tonight, key=lambda r: r["temp_c"])
    ts      = datetime.strptime(coldest["timestamp"], "%Y-%m-%d %H:%M")
    period  = ts.hour * 2 + ts.minute // 30
    return coldest["temp_c"], period


def analyse_meter(meter_id: int, weather_rows: list[dict]) -> dict:
    consumption = load_consumption(meter_id)
    readings    = _to_readings(consumption)
    baseline    = overnight_baseline_kwh(readings)

    # Micro-leak: last 48 overnight periods
    recent_overnight = [kwh for _, p, kwh in readings[-200:] if p in OVERNIGHT_PERIODS]
    if baseline.get("status") == "insufficient_data" or not recent_overnight:
        leak_result = {"alert": False, "max_consecutive_periods": 0,
                       "annualised_waste_kwh": 0, "status": "insufficient_data"}
    else:
        leak_result = detect_gas_leak(recent_overnight, baseline)
        leak_result["status"] = "ok"

    # Frost
    recent_hourly          = _recent_hourly_gas(consumption)
    forecast_low, min_per  = _forecast_overnight_low(weather_rows)
    frost_result           = frost_alert(recent_hourly, forecast_low, min_per)

    # Heating failure frost check
    today_hdd = daily_hdd(forecast_low)
    last_period_gas = recent_overnight[-1] if recent_overnight else 0.0
    expected_heating = today_hdd > 2.0 and 12 <= datetime.now().hour < 22
    hf_result = heating_failure_frost_alert(
        expected_heating, last_period_gas, forecast_low, forecast_low
    )

    leak_alert  = leak_result.get("alert", False)
    frost_alert_ = frost_result.get("alert", False) or hf_result.get("alert", False)
    severity    = (frost_result.get("severity") or hf_result.get("severity") or "")

    print(f"  M{meter_id}: "
          f"leak={'ALERT' if leak_alert else 'ok'} "
          f"(consec={leak_result.get('max_consecutive_periods', 0)}, "
          f"waste={leak_result.get('annualised_waste_kwh', 0)} kWh/yr)  "
          f"frost={'ALERT ' + severity if frost_alert_ else 'ok'} "
          f"(low={forecast_low:.1f}°C)")

    return {
        "meter_id":               meter_id,
        "leak_alert":             leak_alert,
        "max_consecutive_periods": leak_result.get("max_consecutive_periods", 0),
        "annualised_waste_kwh":   leak_result.get("annualised_waste_kwh", 0),
        "frost_alert":            frost_alert_,
        "frost_severity":         severity,
        "forecast_low_c":         round(forecast_low, 1),
        "hours_until_minimum":    round(min_per * 0.5, 1),
        "status":                 leak_result.get("status", "ok"),
    }


def main():
    print("Service #10 — Micro-Leak and Frost Detection\n")
    weather_rows = load_weather()
    fields = ["meter_id", "leak_alert", "max_consecutive_periods",
              "annualised_waste_kwh", "frost_alert", "frost_severity",
              "forecast_low_c", "hours_until_minimum", "status"]
    rows = []
    for meter_id in sorted(METERS):
        rows.append(analyse_meter(meter_id, weather_rows))

    with open(OUT_FILE, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows([{f: r.get(f, "") for f in fields} for r in rows])
    print(f"\nWrote {len(rows)} rows to {OUT_FILE}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_s10_leak_frost.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Smoke-test**

```bash
python py/s10_leak_frost.py
```

Expected: per-meter leak/frost summary + `data/s10_leak_frost.csv` written.

- [ ] **Step 6: Commit**

```bash
git add py/s10_leak_frost.py tests/test_s10_leak_frost.py
git commit -m "feat: add s10_leak_frost — overnight micro-leak detection and frost alerts"
```

---

## Task 7: s09_prewarm.py — Heating Pre-Warm Optimisation

**Files:**
- Create: `py/s09_prewarm.py`
- Create: `tests/test_s09_prewarm.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_s09_prewarm.py`:

```python
import pytest
from s09_prewarm import (
    extract_boiler_start,
    is_smart_thermostat_present,
    recommend_start_time,
)


# --- extract_boiler_start ---

def test_extract_boiler_start_finds_first():
    # period 4 (02:00) has gas, period 6 also — should return 4
    periods = [(0, 0.0), (2, 0.0), (4, 0.20), (6, 0.25), (14, 0.30)]
    assert extract_boiler_start(periods) == 4

def test_extract_boiler_start_none_if_below_threshold():
    periods = [(0, 0.05), (4, 0.10), (8, 0.05)]
    assert extract_boiler_start(periods) is None

def test_extract_boiler_start_only_morning_window():
    # period 26 = 13:00 — outside 0–23 window
    periods = [(26, 0.50), (4, 0.05)]
    assert extract_boiler_start(periods) is None


# --- is_smart_thermostat_present ---

def test_smart_thermostat_detected_low_variance():
    # All starts at period 14 ± 0 → std = 0 < 2
    obs = [(14, t) for t in range(0, 20)]
    assert is_smart_thermostat_present(obs) is True

def test_smart_thermostat_not_detected_high_variance():
    import random
    random.seed(42)
    obs = [(14 + random.randint(-5, 5), t) for t in range(0, 20)]
    assert is_smart_thermostat_present(obs) is False

def test_smart_thermostat_insufficient_obs():
    obs = [(14, t) for t in range(0, 10)]   # < 20
    assert is_smart_thermostat_present(obs) is False


# --- recommend_start_time ---

def test_recommend_clamps_before_target():
    # slope=-1, intercept=20, temp=5 → predicted=15; target=14 → clamp to 13
    result = recommend_start_time(
        forecast_temp=5.0, slope=-1.0, intercept=20.0,
        target_period=14, r_squared=0.80,
    )
    assert result["recommended_start_period"] <= 13

def test_recommend_insufficient_r2():
    result = recommend_start_time(
        forecast_temp=5.0, slope=-1.0, intercept=20.0,
        target_period=14, r_squared=0.30,
    )
    assert result["recommendation"] is None
    assert "insufficient_pattern" in result["reason"]

def test_recommend_clamped_to_zero():
    # Very cold day → predicted start before midnight → clamp to 0
    result = recommend_start_time(
        forecast_temp=-10.0, slope=-2.0, intercept=5.0,
        target_period=14, r_squared=0.90,
    )
    assert result["recommended_start_period"] >= 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_s09_prewarm.py -v 2>&1 | head -10
```

Expected: `ImportError`

- [ ] **Step 3: Create py/s09_prewarm.py**

```python
"""
Service #9 — Heating Pre-Warm Optimisation.

Learns when the boiler fires each morning from historical gas data and fits
a regression against 06:00 outdoor temperature. Uses today's forecast to
recommend tomorrow's optimal start time.

Run: python py/s09_prewarm.py
Outputs: data/s09_prewarm.csv
"""

import csv
import math
from datetime import datetime

from config import METERS, REGRESSION_START, REGRESSION_END
from tier2_lib import (
    load_consumption,
    load_weather,
    fit_hdd_regression,
    period_to_time,
)

OUT_FILE          = "data/s09_prewarm.csv"
BOILER_ON_KWH     = 0.15
MORNING_PERIODS   = range(0, 24)   # 00:00–12:00
MIN_R2            = 0.45
MIN_OBSERVATIONS  = 40
MAX_HISTORY       = 120
SMART_THERM_STD   = 2.0
SMART_THERM_MIN   = 20


def extract_boiler_start(daily_periods: list[tuple[int, float]]) -> int | None:
    for period, kwh in sorted(daily_periods):
        if period in MORNING_PERIODS and kwh >= BOILER_ON_KWH:
            return period
    return None


def is_smart_thermostat_present(observations: list[tuple[int, float]]) -> bool:
    if len(observations) < SMART_THERM_MIN:
        return False
    starts = [o[0] for o in observations]
    mean   = sum(starts) / len(starts)
    std    = math.sqrt(sum((s - mean) ** 2 for s in starts) / len(starts))
    return std < SMART_THERM_STD


def recommend_start_time(forecast_temp: float,
                           slope: float,
                           intercept: float,
                           target_period: int,
                           r_squared: float) -> dict:
    if r_squared < MIN_R2:
        return {"recommendation": None, "reason": "insufficient_pattern",
                "message": "Not enough consistent data to predict optimal start time yet."}
    predicted = int(round(slope * forecast_temp + intercept))
    predicted = max(0, min(predicted, target_period - 1))
    uncertainty = max(2, int(4 * (1 - r_squared)))
    return {
        "recommended_start_period": predicted,
        "recommended_start_time":   period_to_time(predicted),
        "target_period":            target_period,
        "forecast_temp_c":          round(forecast_temp, 1),
        "uncertainty_periods":      uncertainty,
        "message": (f"Turn heating on at {period_to_time(predicted)} "
                    f"({forecast_temp:.0f}°C forecast)."),
    }


def _build_observations(meter_id: int) -> list[tuple[int, float]]:
    """Return [(boiler_start_period, temp_at_0600)] for each heating day."""
    consumption = load_consumption(meter_id)
    weather     = load_weather()

    # Build temp lookup: date → 06:00 temp
    temp_at_0600: dict[str, float] = {}
    for r in weather:
        if r["timestamp"][11:16] == "06:00":
            temp_at_0600[r["timestamp"][:10]] = r["temp_c"]

    # Group consumption by date
    by_date: dict[str, list[tuple[int, float]]] = {}
    for r in consumption:
        ts  = datetime.strptime(r["timestamp"], "%Y-%m-%d %H:%M")
        d   = r["timestamp"][:10]
        if d < REGRESSION_START or d > REGRESSION_END:
            continue
        per = ts.hour * 2 + ts.minute // 30
        by_date.setdefault(d, []).append((per, r["gas_kwh"]))

    obs = []
    for d in sorted(by_date):
        start = extract_boiler_start(by_date[d])
        if start is None or d not in temp_at_0600:
            continue
        obs.append((start, temp_at_0600[d]))

    return obs[-MAX_HISTORY:]


def _today_forecast_temp() -> float:
    """Return today's 06:00 forecast temperature, or climatological fallback."""
    from datetime import date
    today = date.today().isoformat()
    for r in load_weather():
        if r["timestamp"][:10] == today and r["timestamp"][11:16] == "06:00":
            return r["temp_c"]
    return 8.0   # mild fallback


def analyse_meter(meter_id: int) -> dict:
    obs = _build_observations(meter_id)

    if is_smart_thermostat_present(obs):
        print(f"  M{meter_id}: smart thermostat detected — service suppressed")
        return {"meter_id": meter_id, "status": "smart_thermostat_detected",
                "smart_thermostat_detected": True}

    if len(obs) < MIN_OBSERVATIONS:
        print(f"  M{meter_id}: insufficient observations ({len(obs)})")
        return {"meter_id": meter_id, "status": "insufficient_data",
                "smart_thermostat_detected": False}

    # Fit: start_period = slope * temp + intercept
    records = [(temp, float(start)) for start, temp in obs]
    slope, intercept, r_sq = fit_hdd_regression(records)

    forecast_temp = _today_forecast_temp()
    target_period = 14   # 07:00 default — when home should be warm

    result = recommend_start_time(forecast_temp, slope, intercept, target_period, r_sq)

    print(f"  M{meter_id}: R²={r_sq:.2f}  "
          f"obs={len(obs)}  "
          f"forecast={forecast_temp:.1f}°C  "
          + (f"start={result['recommended_start_time']} "
             f"(±{result['uncertainty_periods']} periods)"
             if result.get("recommendation") is not False else result.get("message", "")))

    return {
        "meter_id":                meter_id,
        "recommended_start_time":  result.get("recommended_start_time", ""),
        "recommended_start_period": result.get("recommended_start_period", ""),
        "forecast_temp_c":         forecast_temp,
        "r_squared":               round(r_sq, 3),
        "uncertainty_periods":     result.get("uncertainty_periods", ""),
        "smart_thermostat_detected": False,
        "status":                  "ok" if result.get("recommended_start_time") else "insufficient_pattern",
    }


def main():
    print("Service #9 — Heating Pre-Warm Optimisation\n")
    fields = ["meter_id", "recommended_start_time", "recommended_start_period",
              "forecast_temp_c", "r_squared", "uncertainty_periods",
              "smart_thermostat_detected", "status"]
    rows = []
    for meter_id in sorted(METERS):
        rows.append(analyse_meter(meter_id))

    with open(OUT_FILE, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows([{f: r.get(f, "") for f in fields} for r in rows])
    print(f"\nWrote {len(rows)} rows to {OUT_FILE}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_s09_prewarm.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Smoke-test**

```bash
python py/s09_prewarm.py
```

Expected: per-meter recommendation or suppression reason + `data/s09_prewarm.csv` written.

- [ ] **Step 6: Commit**

```bash
git add py/s09_prewarm.py tests/test_s09_prewarm.py
git commit -m "feat: add s09_prewarm — boiler start-time optimisation from historical gas pattern"
```

---

## Task 8: s08_carbon_shifting.py + appliances.csv

**Files:**
- Create: `data/appliances.csv`
- Create: `py/s08_carbon_shifting.py`
- Create: `tests/test_s08_carbon_shifting.py`

- [ ] **Step 1: Create data/appliances.csv**

```
meter_id,appliance,typical_kwh,min_periods,earliest_period,latest_period
1,washing_machine,1.0,4,0,30
1,dishwasher,1.2,3,32,47
2,washing_machine,1.0,4,0,30
3,washing_machine,1.0,4,0,30
4,dishwasher,1.2,3,32,47
5,ev_charger,7.4,14,0,16
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_s08_carbon_shifting.py`:

```python
import pytest
from s08_carbon_shifting import optimal_shift_window


def _carbon(intensities: list[float]) -> list[dict]:
    return [
        {"period_index": i, "intensity_gco2": v}
        for i, v in enumerate(intensities)
    ]

def _load(min_periods=2, earliest=0, latest=5):
    return {
        "appliance":           "washing_machine",
        "typical_kwh":         1.0,
        "min_periods":         min_periods,
        "earliest_period":     earliest,
        "latest_period":       latest,
    }


def test_finds_lowest_carbon_window():
    # intensities: period 3-4 are lowest
    intensities = [200, 180, 160, 80, 90, 170, 200, 200]
    result = optimal_shift_window(_carbon(intensities), _load(min_periods=2, earliest=0, latest=7))
    assert result["recommended_start_period"] == 3

def test_window_respects_earliest_latest():
    intensities = [50, 50, 200, 200, 200, 200]   # low at 0-1 but earliest=2
    result = optimal_shift_window(_carbon(intensities), _load(min_periods=2, earliest=2, latest=5))
    assert result["recommended_start_period"] >= 2

def test_insufficient_window():
    intensities = [200, 200]
    result = optimal_shift_window(_carbon(intensities), _load(min_periods=3, earliest=0, latest=1))
    assert result["recommendation"] is None

def test_carbon_saving_computed():
    intensities = [200] * 4 + [100] * 4
    # earliest=0, so "current" carbon = mean of periods 0-1 = 200
    # best window at periods 4-5 = 100 → saving = (200-100)*1.0 = 100g
    result = optimal_shift_window(_carbon(intensities), _load(min_periods=2, earliest=0, latest=7))
    assert result["carbon_saving_gco2"] > 0
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
python -m pytest tests/test_s08_carbon_shifting.py -v 2>&1 | head -10
```

Expected: `ImportError`

- [ ] **Step 4: Create py/s08_carbon_shifting.py**

```python
"""
Service #8 — Carbon-Aware Demand Shifting.

Fetches half-hourly carbon intensity for the West Yorkshire DNO region
and recommends when to run each flexible appliance to minimise carbon.

Run: python py/s08_carbon_shifting.py
Outputs: data/s08_carbon_shifting.csv
Requires: data/appliances.csv, internet access to carbonintensity.org.uk
"""

import csv
import json
import urllib.request
from datetime import datetime, timezone

from config import CARBON_REGION_ID, METERS
from tier2_lib import period_to_time

OUT_FILE      = "data/s08_carbon_shifting.csv"
APPLIANCES_IN = "data/appliances.csv"
CARBON_API    = ("https://api.carbonintensity.org.uk/regional/intensity/"
                 "{from_ts}/{to_ts}/regionid/{region_id}")


def fetch_carbon_intensity(region_id: int) -> list[dict]:
    """Return 48h of half-hourly carbon intensity data for the given region."""
    now      = datetime.now(timezone.utc)
    from_ts  = now.strftime("%Y-%m-%dT%H:%MZ")
    to_ts    = datetime.fromtimestamp(
        now.timestamp() + 48 * 3600, tz=timezone.utc
    ).strftime("%Y-%m-%dT%H:%MZ")
    url = CARBON_API.format(from_ts=from_ts, to_ts=to_ts, region_id=region_id)
    with urllib.request.urlopen(url, timeout=15) as resp:
        data = json.loads(resp.read())
    periods = []
    for i, entry in enumerate(data["data"]["data"]):
        periods.append({
            "period_index":   i % 48,
            "intensity_gco2": entry["intensity"]["forecast"],
            "timestamp":      entry["from"],
        })
    return periods


def optimal_shift_window(carbon_periods: list[dict], load: dict) -> dict:
    """
    Find the lowest-carbon contiguous block of min_periods within
    [earliest_period, latest_period].
    """
    window = [cp for cp in carbon_periods
              if load["earliest_period"] <= cp["period_index"] <= load["latest_period"]]

    min_p = load["min_periods"]
    if len(window) < min_p:
        return {"recommendation": None, "reason": "insufficient_window"}

    best_start = 0
    best_carbon = float("inf")
    for i in range(len(window) - min_p + 1):
        block = window[i: i + min_p]
        if block[-1]["period_index"] - block[0]["period_index"] == min_p - 1:
            mean_c = sum(p["intensity_gco2"] for p in block) / min_p
            if mean_c < best_carbon:
                best_carbon = mean_c
                best_start  = i

    best_block = window[best_start: best_start + min_p]

    # "current" carbon: intensity at earliest_period window
    earliest_block = window[:min_p]
    current_carbon = (sum(p["intensity_gco2"] for p in earliest_block) / len(earliest_block)
                      if earliest_block else best_carbon)

    saving = (current_carbon - best_carbon) * load["typical_kwh"]

    return {
        "appliance":                 load["appliance"],
        "recommended_start_period":  best_block[0]["period_index"],
        "recommended_start_time":    period_to_time(best_block[0]["period_index"]),
        "recommended_end_time":      period_to_time(best_block[-1]["period_index"] + 1),
        "mean_carbon_gco2_per_kwh":  round(best_carbon, 0),
        "current_carbon_gco2_per_kwh": round(current_carbon, 0),
        "carbon_saving_gco2":        round(saving, 0),
        "joint_optimal":             True,   # flat tariff → cost-optimal = any window
        "recommendation":            period_to_time(best_block[0]["period_index"]),
    }


def load_appliances() -> list[dict]:
    with open(APPLIANCES_IN, newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["meter_id"]       = int(r["meter_id"])
        r["typical_kwh"]    = float(r["typical_kwh"])
        r["min_periods"]    = int(r["min_periods"])
        r["earliest_period"] = int(r["earliest_period"])
        r["latest_period"]  = int(r["latest_period"])
    return rows


def main():
    print("Service #8 — Carbon-Aware Demand Shifting\n")

    try:
        carbon_periods = fetch_carbon_intensity(CARBON_REGION_ID)
        print(f"  Fetched {len(carbon_periods)} carbon intensity periods")
    except Exception as e:
        print(f"  Carbon API unavailable: {e}")
        print("  Writing empty output.")
        with open(OUT_FILE, "w", newline="") as f:
            csv.DictWriter(f, fieldnames=[
                "meter_id", "appliance", "recommended_start_time",
                "mean_carbon_gco2_per_kwh", "current_carbon_gco2_per_kwh",
                "carbon_saving_gco2", "joint_optimal",
            ]).writeheader()
        return

    appliances = load_appliances()
    rows = []
    for appl in appliances:
        result = optimal_shift_window(carbon_periods, appl)
        if result.get("recommendation") is None:
            print(f"  M{appl['meter_id']} {appl['appliance']}: insufficient window")
            continue
        print(f"  M{appl['meter_id']} {appl['appliance']}: "
              f"best start={result['recommended_start_time']}  "
              f"carbon={result['mean_carbon_gco2_per_kwh']}g/kWh  "
              f"saving={result['carbon_saving_gco2']}g CO₂")
        rows.append({
            "meter_id":                 appl["meter_id"],
            "appliance":                appl["appliance"],
            "recommended_start_time":   result["recommended_start_time"],
            "mean_carbon_gco2_per_kwh": result["mean_carbon_gco2_per_kwh"],
            "current_carbon_gco2_per_kwh": result["current_carbon_gco2_per_kwh"],
            "carbon_saving_gco2":       result["carbon_saving_gco2"],
            "joint_optimal":            result["joint_optimal"],
        })

    fields = ["meter_id", "appliance", "recommended_start_time",
              "mean_carbon_gco2_per_kwh", "current_carbon_gco2_per_kwh",
              "carbon_saving_gco2", "joint_optimal"]
    with open(OUT_FILE, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"\nWrote {len(rows)} rows to {OUT_FILE}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests**

```bash
python -m pytest tests/test_s08_carbon_shifting.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Smoke-test**

```bash
python py/s08_carbon_shifting.py
```

Expected: per-appliance recommendations printed + `data/s08_carbon_shifting.csv` written. (If offline, graceful error message printed and empty CSV written.)

- [ ] **Step 7: Run full test suite**

```bash
python -m pytest tests/ -v
```

Expected: all tests pass (new and existing).

- [ ] **Step 8: Commit**

```bash
git add py/s08_carbon_shifting.py tests/test_s08_carbon_shifting.py data/appliances.csv
git commit -m "feat: add s08_carbon_shifting — carbon-aware appliance scheduling with live ESO API"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|---|---|
| config.py: CARBON_REGION_ID, METER_META | Task 1 |
| tier2_lib: daily_hdd, period_hdd, effective_temp | Task 2 |
| tier2_lib: fit_hdd_regression, period_to_time, UK_BENCHMARKS, benchmark_percentile | Task 2 |
| tier2_lib: load_weather, load_consumption, build_daily_gas_hdd | Task 2 |
| s06: HDD regression, daily score, anomaly triage, benchmark | Task 3 |
| s05: boiler degradation, classify_trend | Task 4 |
| s07: 12-month budget, projection, thermostat nudge | Task 5 |
| s10: overnight baseline, leak detection, frost (vacant + heating failure) | Task 6 |
| s09: boiler start extraction, smart thermostat detection, regression, recommendation | Task 7 |
| s08: carbon API, optimal_shift_window, appliances.csv | Task 8 |
| All scripts: CSV output | Tasks 3–8 |
| All scripts: console summary | Tasks 3–8 |

All spec sections covered. ✓

**Type consistency:**
- `fit_hdd_regression` returns `(slope, intercept, r_sq)` — used consistently in s05, s06, s07, s09. ✓
- `build_daily_gas_hdd` returns `list[dict]` with keys `date`, `hdd`, `gas_kwh`, `mean_temp_c` — used consistently in s05, s06, s07. ✓
- `period_to_time` / `time_to_period` — used in s08, s09. ✓
- `optimal_shift_window` takes `carbon_periods: list[dict]` with `period_index`, `intensity_gco2` — consistent with `fetch_carbon_intensity` output and test fixtures. ✓

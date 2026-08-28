# Tier 1 Clean Repository Build Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a new standalone git repository at `C:\Users\steve\projects\tier1\` containing the four Tier 1 smart meter services in a clean `src/` package layout, with tests, sample data, documentation, and a Tier 1-only Streamlit dashboard.

**Architecture:** Python package `smart_meter` under `src/`, split into `core/` (config, battery simulator, weather CSV loader) and `tier1/` (shared lib + four services). Source files are copied from `smart_meter/py/` with imports updated to use the new package paths. Tier 2–4 subpackages exist as empty stubs.

**Tech Stack:** Python 3.11+, Streamlit, Plotly, Pandas, pytest. No external API keys required for Tier 1.

> **Note on home_model.py:** The design spec lists `core/home_model.py` but none of the four Tier 1 services use it — it is a Tier 4 simulation component that depends on `energy_model.py`. It is intentionally omitted from this plan and will be ported when Tier 4 is built out.

---

## File Map

### New files created

| Path | Responsibility |
|---|---|
| `pyproject.toml` | Package metadata and dependencies |
| `README.md` | Project overview and quickstart |
| `app.py` | Streamlit dashboard — Tier 1 views only |
| `src/smart_meter/__init__.py` | Package root |
| `src/smart_meter/core/__init__.py` | Core subpackage |
| `src/smart_meter/core/config.py` | Meter IDs, rates, location constants |
| `src/smart_meter/core/battery_simulator.py` | Battery arbitrage day simulator |
| `src/smart_meter/core/weather.py` | `load_weather_csv()` for reading cached weather CSV |
| `src/smart_meter/tier1/__init__.py` | Tier 1 subpackage |
| `src/smart_meter/tier1/lib.py` | Shared loaders: electricity, solar, gas, tariff, profile building |
| `src/smart_meter/tier1/tariff.py` | Service S01 — E.ON tariff comparison |
| `src/smart_meter/tier1/battery.py` | Service S02 — battery size optimisation |
| `src/smart_meter/tier1/disaggregation.py` | Service S03 — appliance load disaggregation |
| `src/smart_meter/tier1/heat_pump.py` | Service S04 — heat pump suitability scoring |
| `src/smart_meter/tier2/__init__.py` | Stub placeholder |
| `src/smart_meter/tier3/__init__.py` | Stub placeholder |
| `src/smart_meter/tier4/__init__.py` | Stub placeholder |
| `tests/__init__.py` | Test root |
| `tests/core/__init__.py` | Core tests |
| `tests/core/test_battery_simulator.py` | Tests for `simulate_day` |
| `tests/core/test_weather.py` | Tests for `load_weather_csv` |
| `tests/tier1/__init__.py` | Tier 1 tests |
| `tests/tier1/test_lib.py` | Tests for shared lib functions |
| `tests/tier1/test_tariff.py` | Tests for tariff service |
| `tests/tier1/test_battery.py` | Tests for battery service |
| `tests/tier1/test_disaggregation.py` | Tests for disaggregation service |
| `tests/tier1/test_heat_pump.py` | Tests for heat pump service |
| `data/samples/consumption.csv` | Minimal sample electricity + gas rows |
| `data/samples/weather.csv` | Minimal sample weather rows |
| `data/samples/eon_tariffs.json` | Minimal sample tariff structure |
| `data/samples/tariff.csv` | Minimal sample per-period rates |
| `docs/requirements.md` | Data contracts, service I/O, constraints, live data stub |
| `docs/tier1.md` | Feature descriptions and usage guide |

### Import changes (old → new)

| Old import | New import |
|---|---|
| `from config import X` | `from smart_meter.core.config import X` |
| `from tier1_lib import X` | `from smart_meter.tier1.lib import X` |
| `from battery_simulator import X` | `from smart_meter.core.battery_simulator import X` |
| `from tier2_lib import load_consumption, load_weather` | `from smart_meter.tier1.lib import load_gas` and `from smart_meter.core.weather import load_weather_csv` |

---

## Task 1: Initialise the new repository

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: all `__init__.py` stubs listed in the file map

All commands run from `C:\Users\steve\projects\tier1\`.

- [ ] **Step 1: Create the directory and initialise git**

```bash
mkdir C:/Users/steve/projects/tier1
cd C:/Users/steve/projects/tier1
git init
```

Expected: `Initialized empty Git repository in ...`

- [ ] **Step 2: Create pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=70"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "smart-meter"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "streamlit",
    "plotly",
    "pandas",
]

[project.optional-dependencies]
dev = ["pytest", "pytest-cov"]

[tool.setuptools.packages.find]
where = ["src"]
```

- [ ] **Step 3: Create directory skeleton**

```bash
mkdir -p src/smart_meter/core
mkdir -p src/smart_meter/tier1
mkdir -p src/smart_meter/tier2
mkdir -p src/smart_meter/tier3
mkdir -p src/smart_meter/tier4
mkdir -p tests/core
mkdir -p tests/tier1
mkdir -p data/samples
mkdir -p docs
```

- [ ] **Step 4: Create all `__init__.py` stubs**

Create the following files, each containing only `""" """` (empty docstring):

- `src/smart_meter/__init__.py`
- `src/smart_meter/core/__init__.py`
- `src/smart_meter/tier1/__init__.py`
- `src/smart_meter/tier2/__init__.py` — add comment `# Tier 2: weather services (future)`
- `src/smart_meter/tier3/__init__.py` — add comment `# Tier 3: occupancy services (future)`
- `src/smart_meter/tier4/__init__.py` — add comment `# Tier 4: indoor temperature services (future)`
- `tests/__init__.py`
- `tests/core/__init__.py`
- `tests/tier1/__init__.py`

- [ ] **Step 5: Create README.md**

```markdown
# smart-meter

Tier 1 smart meter analytics — four services that run on half-hourly consumption data alone.

## Services

| ID | Service | Output |
|---|---|---|
| S01 | Tariff matching | `data/s01_tariff_matching.csv` |
| S02 | Battery size optimisation | `data/s02_battery_sizing.csv` |
| S03 | Appliance disaggregation | `data/s03_disaggregation.csv` |
| S04 | Heat pump suitability | `data/s04_heat_pump.csv` |

## Quickstart

```bash
pip install -e ".[dev]"
streamlit run app.py
```

## Running a service

```bash
python -m smart_meter.tier1.tariff
python -m smart_meter.tier1.battery
python -m smart_meter.tier1.disaggregation
python -m smart_meter.tier1.heat_pump
```

## Tests

```bash
pytest tests/ -v
```
```

- [ ] **Step 6: Install in editable mode**

```bash
pip install -e ".[dev]"
```

Expected: `Successfully installed smart-meter-0.1.0`

- [ ] **Step 7: Commit**

```bash
git add .
git commit -m "chore: initialise tier1 package skeleton"
```

---

## Task 2: core/config.py

**Files:**
- Create: `src/smart_meter/core/config.py`

Source: `C:\Users\steve\projects\smart_meter\py\config.py` — copy verbatim. No import changes needed (no imports in config.py).

- [ ] **Step 1: Copy config.py**

Copy the entire contents of `smart_meter/py/config.py` into `src/smart_meter/core/config.py`.

The file defines: `METERS`, `METER_MPANS`, `LAT`, `LON`, `WINTER_START`, `WINTER_END`, `REGRESSION_START`, `REGRESSION_END`, `GAS_KWH_PER_M3`, `GAS_RATE_P_KWH`, `ELEC_RATE_P_KWH`, `GAS_CAP_M3`, `ELEC_CAP_KWH`, `CARBON_REGION_ID`, `METER_META`, `ELEC_METERS`, `SOLAR_METERS`, `SEG_RATE_P_KWH`.

- [ ] **Step 2: Verify import works**

```bash
python -c "from smart_meter.core.config import METERS, ELEC_METERS; print(len(METERS), 'gas meters,', len(ELEC_METERS), 'electricity meters')"
```

Expected: `14 gas meters, 15 electricity meters`

- [ ] **Step 3: Commit**

```bash
git add src/smart_meter/core/config.py
git commit -m "feat: add core/config with meter IDs and energy constants"
```

---

## Task 3: core/battery_simulator.py

**Files:**
- Create: `src/smart_meter/core/battery_simulator.py`
- Create: `tests/core/test_battery_simulator.py`

Source: `C:\Users\steve\projects\smart_meter\py\battery_simulator.py` — copy verbatim. No imports to update (stdlib only).

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_battery_simulator.py`:

```python
from smart_meter.core.battery_simulator import simulate_day


def test_flat_tariff_no_saving():
    # flat tariff: no arbitrage opportunity
    cons = [0.1] * 48
    tariff = [24.0] * 48
    result = simulate_day(cons, tariff, battery_capacity_kwh=5.0)
    assert result["daily_saving_p"] == 0.0


def test_two_rate_tariff_produces_saving():
    # cheap overnight (periods 0-15), expensive peak (periods 32-39)
    cons = [0.5] * 48
    tariff = [8.0] * 16 + [24.0] * 16 + [34.0] * 8 + [24.0] * 8
    result = simulate_day(cons, tariff, battery_capacity_kwh=5.0,
                          round_trip_efficiency=0.92, max_c_rate=0.5, min_soc=0.10)
    assert result["daily_saving_p"] > 0
    assert result["charge_cycled_kwh"] > 0
    assert result["peak_kwh_displaced"] > 0


def test_returns_expected_keys():
    cons = [0.2] * 48
    tariff = [24.0] * 48
    result = simulate_day(cons, tariff, battery_capacity_kwh=5.0)
    assert set(result.keys()) == {"daily_saving_p", "charge_cycled_kwh", "peak_kwh_displaced"}
```

- [ ] **Step 2: Run to verify it fails**

```bash
pytest tests/core/test_battery_simulator.py -v
```

Expected: `ImportError` or `ModuleNotFoundError` — `smart_meter.core.battery_simulator` not yet created.

- [ ] **Step 3: Copy battery_simulator.py**

Copy the entire contents of `smart_meter/py/battery_simulator.py` into `src/smart_meter/core/battery_simulator.py`. The file has no imports to update.

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/core/test_battery_simulator.py -v
```

Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add src/smart_meter/core/battery_simulator.py tests/core/test_battery_simulator.py
git commit -m "feat: add core/battery_simulator with arbitrage day simulation"
```

---

## Task 4: core/weather.py

**Files:**
- Create: `src/smart_meter/core/weather.py`
- Create: `tests/core/test_weather.py`
- Create: `data/samples/weather.csv`

The existing `smart_meter/py/weather.py` wraps the Open-Meteo API. For Tier 1 we also need `load_weather_csv()` to read the locally cached `data/weather.csv`. Copy the existing API functions and add the CSV loader.

- [ ] **Step 1: Create sample weather CSV**

Create `data/samples/weather.csv` with these exact contents:

```
timestamp,temp_c,wind_speed_ms,is_forecast
2024-01-15 00:00,3.5,2.1,0
2024-01-15 00:30,3.2,2.0,0
2024-01-15 01:00,3.0,1.9,0
2024-01-15 12:00,7.1,3.2,0
2024-01-15 12:30,7.4,3.5,0
2024-07-15 12:00,18.5,1.5,0
2024-07-15 12:30,18.9,1.6,0
```

- [ ] **Step 2: Write the failing test**

Create `tests/core/test_weather.py`:

```python
import os
from smart_meter.core.weather import load_weather_csv

SAMPLE = os.path.join(os.path.dirname(__file__),
                      "..", "..", "data", "samples", "weather.csv")


def test_load_weather_csv_returns_list():
    rows = load_weather_csv(SAMPLE)
    assert isinstance(rows, list)
    assert len(rows) == 7


def test_load_weather_csv_field_types():
    rows = load_weather_csv(SAMPLE)
    r = rows[0]
    assert isinstance(r["timestamp"], str)
    assert isinstance(r["temp_c"], float)
    assert isinstance(r["wind_speed_ms"], float)
    assert isinstance(r["is_forecast"], int)


def test_load_weather_csv_sorted():
    rows = load_weather_csv(SAMPLE)
    timestamps = [r["timestamp"] for r in rows]
    assert timestamps == sorted(timestamps)
```

- [ ] **Step 3: Run to verify it fails**

```bash
pytest tests/core/test_weather.py -v
```

Expected: `ImportError` — module not yet created.

- [ ] **Step 4: Create core/weather.py**

Copy `smart_meter/py/weather.py` into `src/smart_meter/core/weather.py` then append the following function at the end of the file:

```python
import csv as _csv  # csv already imported at top of original file; this is a reminder

def load_weather_csv(path: str = "data/weather.csv") -> list[dict]:
    """Return half-hourly weather rows from a cached CSV, sorted by timestamp."""
    with open(path, newline="") as f:
        rows = list(_csv.DictReader(f))
    for r in rows:
        r["temp_c"]        = float(r["temp_c"])
        r["wind_speed_ms"] = float(r.get("wind_speed_ms", 0.0))
        r["is_forecast"]   = int(r.get("is_forecast", 0))
    return sorted(rows, key=lambda r: r["timestamp"])
```

**Note:** The original `weather.py` already imports `csv` at the top. Do not add a duplicate import — use the existing one. The `_csv` alias above is just a reminder; in the actual file use `csv`.

Also update the import at the top of `weather.py` from:
```python
from config import LAT, LON
```
to:
```python
from smart_meter.core.config import LAT, LON
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/core/test_weather.py -v
```

Expected: `3 passed`

- [ ] **Step 6: Commit**

```bash
git add src/smart_meter/core/weather.py tests/core/test_weather.py data/samples/weather.csv
git commit -m "feat: add core/weather with load_weather_csv for cached weather data"
```

---

## Task 5: tier1/lib.py

**Files:**
- Create: `src/smart_meter/tier1/lib.py`
- Create: `tests/tier1/test_lib.py`
- Create: `data/samples/consumption.csv`

Source: `smart_meter/py/tier1_lib.py`. Add `load_gas()` to support S04 (replacing the `load_consumption` call from tier2_lib).

- [ ] **Step 1: Create sample consumption CSV**

Create `data/samples/consumption.csv`:

```
mpxn,utility,timestamp,value
1234567891000,electricity,2024-01-15 00:00,0.15
1234567891000,electricity,2024-01-15 00:30,0.12
1234567891000,electricity,2024-01-15 01:00,0.10
1234567891000,electricity,2024-01-15 12:00,0.45
1234567891000,electricity,2024-01-15 12:30,0.50
1234567891000,gas,2024-01-15 00:00,0.05
1234567891000,gas,2024-01-15 00:30,0.06
1234567891000,gas,2024-01-15 12:00,0.20
1234567891000,gas,2024-01-15 12:30,0.22
```

Note: gas values are in m³ (converted to kWh by multiplying by 11.2).

- [ ] **Step 2: Write the failing test**

Create `tests/tier1/test_lib.py`:

```python
import os
from smart_meter.tier1.lib import (
    build_weekly_profile,
    consumption_shape,
    rate_for_period,
    annual_cost_for_tariff,
    load_electricity,
    load_gas,
)

SAMPLE_CSV = os.path.join(os.path.dirname(__file__),
                           "..", "..", "data", "samples", "consumption.csv")


def test_build_weekly_profile_returns_medians():
    readings = [
        {"timestamp": "2024-01-15 00:00", "elec_kwh": 0.2, "weekday": 0, "period_index": 0},
        {"timestamp": "2024-01-22 00:00", "elec_kwh": 0.4, "weekday": 0, "period_index": 0},
    ]
    profile = build_weekly_profile(readings, weeks=9999)
    assert profile[(0, 0)] == 0.3  # median of [0.2, 0.4]


def test_consumption_shape_night_fraction():
    # All consumption in night periods (0-13)
    profile = {(0, p): 1.0 for p in range(14)}
    shape = consumption_shape(profile)
    assert shape["night_fraction"] == 1.0
    assert shape["annual_kwh_estimate"] > 0


def test_rate_for_period_returns_correct_band():
    bands = [
        {"start_period": 0, "end_period": 15, "rate_p_per_kwh": 8.0},
        {"start_period": 16, "end_period": 47, "rate_p_per_kwh": 28.0},
    ]
    assert rate_for_period(bands, 0) == 8.0
    assert rate_for_period(bands, 15) == 8.0
    assert rate_for_period(bands, 16) == 28.0
    assert rate_for_period(bands, 47) == 28.0


def test_annual_cost_scales_to_365():
    readings = [
        {"timestamp": "2024-01-15 00:00", "elec_kwh": 1.0, "period_index": 0},
    ]
    bands = [{"start_period": 0, "end_period": 47, "rate_p_per_kwh": 100.0}]
    result = annual_cost_for_tariff(readings, bands, standing_p_day=0.0)
    # 1 kWh at 100p, 1 day in sample, scaled to 365: 365 * 100p = 36500p = £365
    assert result["unit_cost_gbp"] == 365.0
    assert result["days_in_sample"] == 1


def test_load_electricity_filters_correct_meter():
    # ELEC_METERS[1] == "1234567891000"
    rows = load_electricity(1, path=SAMPLE_CSV)
    assert all(r["elec_kwh"] > 0 for r in rows)
    assert len(rows) == 5


def test_load_gas_returns_kwh_not_m3():
    # METERS[1] == "1234567891000"; gas values are m³ × 11.2
    rows = load_gas(1, path=SAMPLE_CSV)
    assert len(rows) == 4
    # 0.05 m³ × 11.2 = 0.56 kWh
    assert abs(rows[0]["gas_kwh"] - 0.56) < 0.01
```

- [ ] **Step 3: Run to verify it fails**

```bash
pytest tests/tier1/test_lib.py -v
```

Expected: `ImportError` — module not yet created.

- [ ] **Step 4: Create tier1/lib.py**

Copy `smart_meter/py/tier1_lib.py` into `src/smart_meter/tier1/lib.py`.

Update the import at the top from:
```python
from config import ELEC_METERS, ELEC_CAP_KWH, ELEC_RATE_P_KWH, SOLAR_METERS
```
to:
```python
from smart_meter.core.config import (
    ELEC_METERS, ELEC_CAP_KWH, ELEC_RATE_P_KWH, SOLAR_METERS,
    METERS, GAS_KWH_PER_M3, GAS_CAP_M3,
)
```

Then add the following function at the end of the file:

```python
def load_gas(meter_id: int,
             path: str = "data/consumption_clean.csv") -> list[dict]:
    """
    Return half-hourly gas rows for one meter, sorted by timestamp.
    Values are converted from m³ to kWh using GAS_KWH_PER_M3.
    Filters out readings above GAS_CAP_M3.
    """
    mpxn = METERS[meter_id]
    seen: set[str] = set()
    rows = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            if row["mpxn"] != mpxn or row["utility"] != "gas":
                continue
            ts = row["timestamp"]
            if ts in seen:
                continue
            seen.add(ts)
            val = float(row["value"])
            if val > GAS_CAP_M3:
                continue
            rows.append({
                "timestamp": ts,
                "gas_kwh":   round(val * GAS_KWH_PER_M3, 4),
            })
    return sorted(rows, key=lambda r: r["timestamp"])
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/tier1/test_lib.py -v
```

Expected: `6 passed`

- [ ] **Step 6: Commit**

```bash
git add src/smart_meter/tier1/lib.py tests/tier1/test_lib.py \
        data/samples/consumption.csv
git commit -m "feat: add tier1/lib with electricity, gas, solar loaders and profile building"
```

---

## Task 6: tier1/tariff.py (S01)

**Files:**
- Create: `src/smart_meter/tier1/tariff.py`
- Create: `tests/tier1/test_tariff.py`
- Create: `data/samples/eon_tariffs.json`
- Create: `data/samples/tariff.csv`

Source: `smart_meter/py/s01_tariff_matching.py`.

- [ ] **Step 1: Create sample data files**

Create `data/samples/eon_tariffs.json`:

```json
[
  {
    "name": "E.ON Next Fixed",
    "product_type": "actual",
    "standing_p_day": 53.0,
    "bands": [{"start_period": 0, "end_period": 47, "rate_p_per_kwh": 24.5}]
  },
  {
    "name": "E.ON Next Flex",
    "product_type": "flex",
    "standing_p_day": 53.0,
    "bands": [{"start_period": 0, "end_period": 47, "rate_p_per_kwh": 22.0}]
  },
  {
    "name": "E.ON Drive",
    "product_type": "drive",
    "standing_p_day": 60.0,
    "bands": [
      {"start_period": 0, "end_period": 13, "rate_p_per_kwh": 7.5},
      {"start_period": 14, "end_period": 47, "rate_p_per_kwh": 30.0}
    ]
  }
]
```

Create `data/samples/tariff.csv`:

```
mpan,type,timestamp,value
1234567891000,unit_rate,2024-01-01 00:00,24.5
1234567891000,standing_charge,2024-01-01 00:00,0.53
```

- [ ] **Step 2: Write the failing test**

Create `tests/tier1/test_tariff.py`:

```python
from smart_meter.tier1.tariff import (
    rank_alternatives,
    flag_too_close,
    _period_to_time,
)


def _make_readings(n=48):
    return [
        {"timestamp": f"2024-01-15 {h:02d}:{m:02d}", "elec_kwh": 0.3,
         "period_index": h * 2 + m // 30}
        for h in range(24) for m in (0, 30)
    ][:n]


def _make_products():
    return [
        {
            "name": "Actual",
            "product_type": "actual",
            "standing_p_day": 53.0,
            "bands": [{"start_period": 0, "end_period": 47, "rate_p_per_kwh": 24.5}],
        },
        {
            "name": "Cheaper",
            "product_type": "flex",
            "standing_p_day": 53.0,
            "bands": [{"start_period": 0, "end_period": 47, "rate_p_per_kwh": 20.0}],
        },
        {
            "name": "Pricier",
            "product_type": "drive",
            "standing_p_day": 60.0,
            "bands": [{"start_period": 0, "end_period": 47, "rate_p_per_kwh": 28.0}],
        },
    ]


def test_rank_alternatives_excludes_actual():
    readings = _make_readings()
    products = _make_products()
    ranked = rank_alternatives(readings, current_gbp=500.0, eon_products=products)
    names = [r["product"] for r in ranked]
    assert "Actual" not in names
    assert len(ranked) == 2


def test_rank_alternatives_best_saving_first():
    readings = _make_readings()
    products = _make_products()
    ranked = rank_alternatives(readings, current_gbp=500.0, eon_products=products)
    assert ranked[0]["saving_vs_current_gbp"] >= ranked[1]["saving_vs_current_gbp"]


def test_flag_too_close_marks_small_positive_saving():
    ranked = [{"saving_vs_current_gbp": 15.0}, {"saving_vs_current_gbp": 5.0}]
    result = flag_too_close(ranked, threshold_gbp=20.0)
    assert all(r["too_close"] for r in result)


def test_flag_too_close_false_when_no_saving():
    ranked = [{"saving_vs_current_gbp": -10.0}]
    result = flag_too_close(ranked)
    assert not result[0]["too_close"]


def test_period_to_time_boundaries():
    assert _period_to_time(0) == "00:00"
    assert _period_to_time(47) == "23:30"
    assert _period_to_time(24) == "12:00"
```

- [ ] **Step 3: Run to verify it fails**

```bash
pytest tests/tier1/test_tariff.py -v
```

Expected: `ImportError` — module not yet created.

- [ ] **Step 4: Create tier1/tariff.py**

Copy `smart_meter/py/s01_tariff_matching.py` into `src/smart_meter/tier1/tariff.py`.

Replace the imports block (lines 1–23 of the original) with:

```python
"""
Service #1 — E.ON Tariff Comparison.

Run: python -m smart_meter.tier1.tariff
Outputs: data/s01_tariff_matching.csv
"""

import csv
import json

from smart_meter.core.config import METERS, ELEC_METERS, ELEC_RATE_P_KWH, SEG_RATE_P_KWH
from smart_meter.tier1.lib import (
    load_electricity,
    load_solar_generation,
    load_tariff_rates,
    build_weekly_profile,
    consumption_shape,
    annual_cost_for_tariff,
    compute_annual_export,
)

OUT_FILE     = "data/s01_tariff_matching.csv"
TARIFFS_FILE = "data/eon_tariffs.json"
TOO_CLOSE_GBP = 20.0
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/tier1/test_tariff.py -v
```

Expected: `5 passed`

- [ ] **Step 6: Commit**

```bash
git add src/smart_meter/tier1/tariff.py tests/tier1/test_tariff.py \
        data/samples/eon_tariffs.json data/samples/tariff.csv
git commit -m "feat: add tier1/tariff — S01 E.ON tariff comparison service"
```

---

## Task 7: tier1/battery.py (S02)

**Files:**
- Create: `src/smart_meter/tier1/battery.py`
- Create: `tests/tier1/test_battery.py`

Source: `smart_meter/py/s02_battery_sizing.py`.

- [ ] **Step 1: Write the failing test**

Create `tests/tier1/test_battery.py`:

```python
from smart_meter.tier1.battery import (
    build_daily_arrays,
    npv,
    find_recommended,
)


def test_build_daily_arrays_skips_incomplete_days():
    # 47 readings for one day → skipped
    readings = [
        {"timestamp": f"2024-01-15 {h:02d}:{m:02d}", "elec_kwh": 0.2,
         "period_index": h * 2 + m // 30}
        for h in range(24) for m in (0, 30)
    ][:47]
    period_rates = {p: 24.0 for p in range(48)}
    result = build_daily_arrays(readings, period_rates)
    assert result == []


def test_build_daily_arrays_returns_48_element_lists():
    readings = [
        {"timestamp": f"2024-01-15 {h:02d}:{m:02d}", "elec_kwh": 0.3,
         "period_index": h * 2 + m // 30}
        for h in range(24) for m in (0, 30)
    ]
    period_rates = {p: 24.0 for p in range(48)}
    result = build_daily_arrays(readings, period_rates)
    assert len(result) == 1
    cons, tariff = result[0]
    assert len(cons) == 48
    assert len(tariff) == 48


def test_npv_positive_for_good_investment():
    # £200/yr saving on £500 upfront over 10yr at 3.5%
    result = npv(annual_saving=200.0, upfront_cost=500.0, rate=0.035, years=10)
    assert result > 0


def test_npv_negative_for_bad_investment():
    result = npv(annual_saving=10.0, upfront_cost=5000.0, rate=0.035, years=10)
    assert result < 0


def test_find_recommended_shortest_payback():
    curve = [
        {"capacity_kwh": 5.0,  "payback_years": 8.0},
        {"capacity_kwh": 10.0, "payback_years": 6.0},
        {"capacity_kwh": 2.0,  "payback_years": float("inf")},
    ]
    rec = find_recommended(curve)
    assert rec["capacity_kwh"] == 10.0


def test_find_recommended_none_when_all_inf():
    curve = [
        {"capacity_kwh": 5.0, "payback_years": float("inf")},
    ]
    assert find_recommended(curve) is None
```

- [ ] **Step 2: Run to verify it fails**

```bash
pytest tests/tier1/test_battery.py -v
```

Expected: `ImportError` — module not yet created.

- [ ] **Step 3: Create tier1/battery.py**

Copy `smart_meter/py/s02_battery_sizing.py` into `src/smart_meter/tier1/battery.py`.

Replace the imports block with:

```python
"""
Service #2 — Battery Size Optimisation.

Run: python -m smart_meter.tier1.battery
Outputs: data/s02_battery_sizing.csv
"""

import csv

from smart_meter.core.battery_simulator import simulate_day
from smart_meter.core.config import METERS, ELEC_METERS
from smart_meter.tier1.lib import load_electricity, load_tariff_rates

OUT_FILE         = "data/s02_battery_sizing.csv"
CAPACITIES_KWH   = [2.0, 4.0, 5.0, 7.0, 10.0, 13.5]
COST_PER_KWH_GBP = 700
MAX_PAYBACK_YRS  = 15
DISCOUNT_RATE    = 0.035
NPV_YEARS        = 10
```

Remove the `sys.path.insert` lines that were in the original (no longer needed).

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/tier1/test_battery.py -v
```

Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add src/smart_meter/tier1/battery.py tests/tier1/test_battery.py
git commit -m "feat: add tier1/battery — S02 battery size optimisation service"
```

---

## Task 8: tier1/disaggregation.py (S03)

**Files:**
- Create: `src/smart_meter/tier1/disaggregation.py`
- Create: `tests/tier1/test_disaggregation.py`

Source: `smart_meter/py/s03_disaggregation.py`.

- [ ] **Step 1: Write the failing test**

Create `tests/tier1/test_disaggregation.py`:

```python
from smart_meter.tier1.disaggregation import (
    compute_residual,
    detect_events,
    match_event,
    aggregate_appliance_evidence,
    DETECTION_THRESHOLD,
)


def _make_profile():
    return {(wd, p): 0.1 for wd in range(7) for p in range(48)}


def test_compute_residual_clips_negative():
    profile = _make_profile()
    readings = [{"timestamp": "2024-01-15 00:00", "elec_kwh": 0.05,
                 "weekday": 0, "period_index": 0}]
    residual = compute_residual(readings, profile)
    assert residual[0]["residual_kwh"] == 0.0


def test_compute_residual_returns_excess():
    profile = _make_profile()
    readings = [{"timestamp": "2024-01-15 00:00", "elec_kwh": 0.5,
                 "weekday": 0, "period_index": 0}]
    residual = compute_residual(readings, profile)
    assert abs(residual[0]["residual_kwh"] - 0.4) < 0.001


def test_detect_events_groups_consecutive():
    residual = [
        {"date": "2024-01-15", "period_index": 0, "residual_kwh": 0.5},
        {"date": "2024-01-15", "period_index": 1, "residual_kwh": 0.6},
        {"date": "2024-01-15", "period_index": 2, "residual_kwh": 0.0},  # gap
        {"date": "2024-01-15", "period_index": 3, "residual_kwh": 0.4},
    ]
    events = detect_events(residual)
    assert len(events) == 2
    assert events[0]["duration_periods"] == 2


def test_detect_events_empty_when_below_threshold():
    residual = [
        {"date": "2024-01-15", "period_index": p, "residual_kwh": 0.1}
        for p in range(10)
    ]
    events = detect_events(residual)
    assert events == []


def test_match_event_ev_slow_at_night():
    # 8 periods, peak 1.6 kWh, starts at period 2 (01:00) — matches ev_slow
    event = {
        "date": "2024-01-15", "start_period": 2, "end_period": 9,
        "duration_periods": 8, "total_kwh": 12.0,
        "peak_kwh_per_period": 1.6, "mean_kwh_per_period": 1.5,
    }
    matches = match_event(event)
    appliances = [m[0] for m in matches]
    assert "ev_slow" in appliances


def test_aggregate_appliance_evidence_likely_present():
    # Create 5 matching events for ev_slow with high confidence
    events = [
        {"date": "2024-01-15", "start_period": 2, "end_period": 9,
         "duration_periods": 8, "total_kwh": 12.0,
         "peak_kwh_per_period": 1.7, "mean_kwh_per_period": 1.5}
        for _ in range(5)
    ]
    evidence = aggregate_appliance_evidence(events)
    assert evidence.get("ev_slow", {}).get("likely_present", False)
```

- [ ] **Step 2: Run to verify it fails**

```bash
pytest tests/tier1/test_disaggregation.py -v
```

Expected: `ImportError` — module not yet created.

- [ ] **Step 3: Create tier1/disaggregation.py**

Copy `smart_meter/py/s03_disaggregation.py` into `src/smart_meter/tier1/disaggregation.py`.

Replace the imports block with:

```python
"""
Service #3 — Appliance Load Disaggregation.

Run: python -m smart_meter.tier1.disaggregation
Outputs: data/s03_disaggregation.csv
"""

import csv

from smart_meter.core.config import METERS
from smart_meter.tier1.lib import load_electricity, build_weekly_profile

OUT_FILE            = "data/s03_disaggregation.csv"
DETECTION_THRESHOLD = 0.25
MIN_MATCH_COUNT     = 4
MIN_CONFIDENCE      = 0.55
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/tier1/test_disaggregation.py -v
```

Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add src/smart_meter/tier1/disaggregation.py tests/tier1/test_disaggregation.py
git commit -m "feat: add tier1/disaggregation — S03 appliance load detection service"
```

---

## Task 9: tier1/heat_pump.py (S04)

**Files:**
- Create: `src/smart_meter/tier1/heat_pump.py`
- Create: `tests/tier1/test_heat_pump.py`

Source: `smart_meter/py/s04_heat_pump.py`. The key change: replace `from tier2_lib import load_consumption, load_weather` with `load_gas` from `tier1.lib` and `load_weather_csv` from `core.weather`.

- [ ] **Step 1: Write the failing test**

Create `tests/tier1/test_heat_pump.py`:

```python
from smart_meter.tier1.heat_pump import (
    cop_at_outdoor_temp,
    heating_kwh,
    heat_pump_payback,
    suitability_flags,
)


def test_cop_increases_with_outdoor_temp():
    cop_cold = cop_at_outdoor_temp(-5.0, flow_temp=45.0)
    cop_mild = cop_at_outdoor_temp(10.0, flow_temp=45.0)
    assert cop_mild > cop_cold


def test_cop_clamped_at_extreme_cold():
    assert cop_at_outdoor_temp(-15.0) == 1.0


def test_heating_kwh_subtracts_base():
    assert heating_kwh(10.0, 3.0) == 7.0


def test_heating_kwh_clips_negative():
    assert heating_kwh(2.0, 5.0) == 0.0


def test_heat_pump_payback_viable():
    result = heat_pump_payback(
        installed_cost_gbp=12000.0,
        annual_saving_gbp=800.0,
        grant_gbp=7500.0,
    )
    assert result["viable"]
    assert result["net_cost_gbp"] == 4500.0
    assert result["payback_years"] < 15.0


def test_heat_pump_payback_not_viable_no_saving():
    result = heat_pump_payback(
        installed_cost_gbp=12000.0,
        annual_saving_gbp=-100.0,
        grant_gbp=7500.0,
    )
    assert not result["viable"]
    assert result["payback_years"] is None


def test_suitability_flags_returns_four_checks():
    result = {
        "heating_gas_kwh": 8000.0,
        "winter_summer_gas_ratio": 3.0,
        "mean_seasonal_cop": 3.5,
        "breakeven_cop": 4.0,
        "viable": True,
        "payback_years": 7.0,
    }
    flags = suitability_flags(result)
    assert len(flags) == 4
    check_names = {f["check"] for f in flags}
    assert check_names == {
        "annual_heating_demand", "seasonal_signal",
        "cop_above_breakeven", "financial_viability",
    }
```

- [ ] **Step 2: Run to verify it fails**

```bash
pytest tests/tier1/test_heat_pump.py -v
```

Expected: `ImportError` — module not yet created.

- [ ] **Step 3: Create tier1/heat_pump.py**

Copy `smart_meter/py/s04_heat_pump.py` into `src/smart_meter/tier1/heat_pump.py`.

Replace the imports block with:

```python
"""
Service #4 — Heat Pump Suitability Scoring.

Run: python -m smart_meter.tier1.heat_pump
Outputs: data/s04_heat_pump.csv
"""

import csv
import statistics
from datetime import datetime, date as date_type

from smart_meter.core.config import METERS, ELEC_METERS, GAS_RATE_P_KWH, ELEC_RATE_P_KWH
from smart_meter.core.weather import load_weather_csv
from smart_meter.tier1.lib import load_tariff_rates, load_gas

OUT_FILE          = "data/s04_heat_pump.csv"
BOILER_EFFICIENCY = 0.89
ETA_ASHP          = 0.45
GRANT_GBP         = 7500
INSTALLED_COST_GBP = 12000
DISCOUNT_RATE     = 0.035
NPV_YEARS         = 15
HEATING_SEASON_MONTHS = {10, 11, 12, 1, 2, 3}
SUMMER_MONTHS         = {5, 6, 7, 8, 9}
```

Then update the two internal helper functions that call the old loaders:

Replace `_build_daily_gas`:
```python
def _build_daily_gas(meter_id: int) -> dict[date_type, float]:
    rows = load_gas(meter_id)
    daily: dict[date_type, float] = {}
    for r in rows:
        d = date_type.fromisoformat(r["timestamp"][:10])
        daily[d] = daily.get(d, 0.0) + r["gas_kwh"]
    return daily
```

Replace `_build_daily_weather`:
```python
def _build_daily_weather() -> dict[date_type, float]:
    daily_temps: dict[date_type, list[float]] = {}
    for r in load_weather_csv():
        if r.get("is_forecast"):
            continue
        d = date_type.fromisoformat(r["timestamp"][:10])
        daily_temps.setdefault(d, []).append(r["temp_c"])
    return {d: sum(v) / len(v) for d, v in daily_temps.items()}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/tier1/test_heat_pump.py -v
```

Expected: `7 passed`

- [ ] **Step 5: Run the full test suite**

```bash
pytest tests/ -v
```

Expected: all tests pass (currently: 3 + 3 + 6 + 5 + 6 + 6 + 7 = 36 tests).

- [ ] **Step 6: Commit**

```bash
git add src/smart_meter/tier1/heat_pump.py tests/tier1/test_heat_pump.py
git commit -m "feat: add tier1/heat_pump — S04 heat pump suitability service"
```

---

## Task 10: Documentation

**Files:**
- Create: `docs/requirements.md`
- Create: `docs/tier1.md`

- [ ] **Step 1: Create docs/requirements.md**

```markdown
# Requirements

## 1. Data Requirements

### 1.1 Current: Static Half-Hourly CSV

**Electricity and gas consumption** (`data/consumption_clean.csv`):

| Column | Type | Format | Notes |
|---|---|---|---|
| mpxn | str | — | Meter Point Administration Number |
| utility | str | `electricity` or `gas` | Filter on this value |
| timestamp | str | `YYYY-MM-DD HH:MM` | 48 readings per day |
| value | float | kWh (electricity) or m³ (gas) | Gas values converted to kWh via GAS_KWH_PER_M3 = 11.2 |

Gas readings above `GAS_CAP_M3 = 2.0` m³/period are filtered as outliers.  
Electricity readings above `ELEC_CAP_KWH = 15.0` kWh/period are filtered as outliers.

**Solar generation** (`data/production_clean.csv`):

| Column | Type | Format | Notes |
|---|---|---|---|
| mpxn | str | — | Solar meter MPXN |
| timestamp | str | `YYYY-MM-DD HH:MM` | Half-hourly |
| value | float | kWh | Generation in the period |

Only meters listed in `SOLAR_METERS` have solar data. Returns `[]` for others.

**Tariff rates** (`data/eon_tariffs.json`):

JSON array of product objects:
```json
{
  "name": "Product Name",
  "product_type": "actual | fixed | drive | flex",
  "standing_p_day": 53.0,
  "bands": [
    {"start_period": 0, "end_period": 47, "rate_p_per_kwh": 24.5}
  ]
}
```
`product_type = "actual"` is the meter's current tariff (the reference). All others are alternatives to rank.

**Per-meter tariff rates** (`data/tariff.csv`):

| Column | Type | Notes |
|---|---|---|
| mpan | str | Electricity MPAN |
| type | str | `unit_rate` or `standing_charge` |
| timestamp | str | `YYYY-MM-DD HH:MM` |
| value | float | p/kWh for unit_rate; £/day for standing_charge |

**Weather** (`data/weather.csv`):

| Column | Type | Notes |
|---|---|---|
| timestamp | str | `YYYY-MM-DD HH:MM` |
| temp_c | float | Outdoor air temperature |
| wind_speed_ms | float | Wind speed in m/s |
| is_forecast | int | 0 = historical, 1 = forecast |

Required only by S04 (heat pump). Produced by `smart_meter.core.weather` via Open-Meteo API.

**Minimum data volume:**
- 7 complete days (48 readings each) per meter for S02 (battery sizing).
- 8 weeks preferred for stable weekly profile in S01, S03, S04.
- S04 requires gas data spanning at least one full heating season (Oct–Mar) and one summer (May–Sep) to estimate base load.

### 1.2 Future: Live / Streaming Data

*This section is reserved. Live data integration is a significant separate workstream, out of scope for this release.*

Key considerations when this is tackled:

- **Polling cadence:** Smart meter data is available with a 24–48 hour lag via the DCC/IHD API; half-hourly resolution requires daily batch pulls, not true streaming.
- **Authentication:** DCC API requires household enrollment and OAuth-style credentials per MPAN.
- **Data normalisation:** Live feeds may differ from the cleaned CSV format in field names, timezone handling, and gap patterns. A normalisation layer will be required.
- **Backfill strategy:** First run will need to pull historical data to build the 8-week weekly profile window. Incremental pulls thereafter.

---

## 2. Service Contracts

### S01 — Tariff Matching

**Entry point:** `python -m smart_meter.tier1.tariff`  
**Inputs:** `data/consumption_clean.csv`, `data/tariff.csv`, `data/eon_tariffs.json`, `data/production_clean.csv`  
**Output:** `data/s01_tariff_matching.csv`

One row per (meter, product) pair. The `actual` row (rank 0) is the current tariff. Alternatives ranked 1–N by saving.

| Column | Type | Description |
|---|---|---|
| meter_id | int | Meter identifier |
| product | str | Tariff product name |
| type | str | `actual`, `actual (default)`, `fixed`, `drive`, `flex` |
| rates | str | Human-readable rate summary |
| current_annual_cost_gbp | float | Annualised spend on current tariff |
| annual_cost_gbp | float | Annualised spend on this product |
| saving_vs_current_gbp | float | Positive = saving, negative = more expensive |
| saving_pct | float | Percentage saving vs current |
| night_fraction | float | Fraction of consumption 00:00–06:59 |
| too_close | bool | True if best saving is positive but < £20 |
| rank | int | 0 = actual tariff, 1 = best alternative |
| seg_earnings_gbp | float | Annual Smart Export Guarantee earnings |
| net_cost_gbp | float | annual_cost_gbp minus seg_earnings_gbp |

### S02 — Battery Size Optimisation

**Entry point:** `python -m smart_meter.tier1.battery`  
**Inputs:** `data/consumption_clean.csv`, `data/tariff.csv`  
**Output:** `data/s02_battery_sizing.csv`

One row per (meter, capacity) pair. Sweeps: 2, 4, 5, 7, 10, 13.5 kWh.

| Column | Type | Description |
|---|---|---|
| meter_id | int | Meter identifier |
| capacity_kwh | float | Battery size |
| installed_cost_gbp | float | Capacity × £700/kWh |
| annual_saving_gbp | float | Simulated arbitrage saving per year |
| payback_years | float | Simple payback; `inf` if no saving |
| npv_10yr_gbp | float | Net present value over 10 years at 3.5% discount |
| recommended | bool | True for shortest payback ≤ 15 years |

### S03 — Appliance Load Disaggregation

**Entry point:** `python -m smart_meter.tier1.disaggregation`  
**Inputs:** `data/consumption_clean.csv`  
**Output:** `data/s03_disaggregation.csv`

One row per (meter, appliance) pair. Appliances: `ev_fast`, `ev_slow`, `immersion`, `shower`, `washing`, `dishwasher`, `oven`.

| Column | Type | Description |
|---|---|---|
| meter_id | int | Meter identifier |
| appliance | str | Appliance type |
| match_count | int | Number of residual events matched |
| mean_confidence | float | Mean match score (0–1) |
| likely_present | bool | True if count ≥ 4 and mean_confidence ≥ 0.55 |

### S04 — Heat Pump Suitability

**Entry point:** `python -m smart_meter.tier1.heat_pump`  
**Inputs:** `data/consumption_clean.csv`, `data/tariff.csv`, `data/weather.csv`  
**Output:** `data/s04_heat_pump.csv`

Two rows per meter (optimistic 45°C flow temp, conservative 55°C flow temp).

| Column | Type | Description |
|---|---|---|
| meter_id | int | Meter identifier |
| scenario | str | `optimistic_45c_flow` or `conservative_55c_flow` |
| heating_gas_kwh | float | Annual heating demand (above summer base load) |
| hp_elec_kwh | float | Estimated annual heat pump electricity |
| gas_cost_gbp | float | Current annual heating cost (gas) |
| hp_elec_cost_gbp | float | Projected heat pump electricity cost |
| annual_saving_gbp | float | gas_cost minus hp_elec_cost |
| mean_seasonal_cop | float | Effective seasonal COP |
| breakeven_cop | float | electricity_rate / gas_rate |
| payback_years | float | Net cost after £7,500 grant / annual saving |
| npv_15yr_gbp | float | NPV over 15 years at 3.5% discount |
| viable | bool | payback ≤ 15 yrs and NPV > 0 |
| flag_heating_demand | bool | Annual heating demand ≥ 5,000 kWh |
| flag_seasonal_signal | bool | Winter/summer gas ratio ≥ 2.0 |
| flag_cop_above_breakeven | bool | Mean COP ≥ electricity/gas price ratio |
| flag_financial_viability | bool | Payback ≤ 15 years |

---

## 3. Dependencies

- Python 3.11+
- streamlit
- plotly
- pandas
- pytest, pytest-cov (dev only)

No external API keys are required for Tier 1 services. S04 uses weather data from a locally cached CSV. The `smart_meter.core.weather` module can refresh this cache from the Open-Meteo public API (no key required).

---

## 4. Constraints

Tier 1 services do **not** require:

- Indoor temperature sensors (Tier 4)
- Occupancy detection hardware (Tier 3)
- Proprietary weather data subscriptions
- Cloud infrastructure or a database — all services run locally against flat files

---

## 5. Growth Path

| Tier | Additional requirement | New subpackage | Services |
|---|---|---|---|
| 2 | Outdoor temperature (weather API or CSV) | `smart_meter.tier2` | Boiler trending, heating efficiency, budget forecast, carbon shifting, pre-warm, leak/frost |
| 3 | Occupancy detection | `smart_meter.tier3` | Anomaly suppression, occupancy-adjusted profiles |
| 4 | Indoor temperature sensors | `smart_meter.tier4` | Thermal comfort, zone control, HTC fitting |
```

- [ ] **Step 2: Create docs/tier1.md**

```markdown
# Tier 1 Smart Meter Services

Four analytics services that run on half-hourly smart meter data alone — no additional sensors or proprietary feeds required.

## S01 — Tariff Matching

Compares a household's actual consumption against available E.ON tariff products and ranks them by projected annual cost.

**How it works:** Builds a half-hourly consumption profile from the last 8 weeks of readings. Applies each tariff's band rates to the actual consumption pattern. Scales to an annual cost estimate. Ranks alternatives by saving vs the current tariff.

**Key output:** `saving_vs_current_gbp` per product. `too_close=True` when the best saving is positive but under £20 — not worth switching.

**Run:** `python -m smart_meter.tier1.tariff`

## S02 — Battery Size Optimisation

Sweeps battery capacities from 2–13.5 kWh and finds the size with the shortest payback period under 15 years.

**How it works:** Simulates one year of daily battery arbitrage using the household's actual half-hourly tariff rates. Models round-trip efficiency (92%), C-rate limits, and minimum state of charge. Computes NPV at 3.5% over 10 years.

**Key output:** `recommended=True` on the row with shortest viable payback. `payback_years=inf` means no arbitrage saving is achievable.

**Run:** `python -m smart_meter.tier1.battery`

## S03 — Appliance Load Disaggregation

Detects appliance signatures in the electricity consumption pattern by identifying residual load events above the baseline weekly profile.

**How it works:** Subtracts the median weekly profile from each reading to isolate unexpected load bursts. Matches each burst against appliance signatures (duration range, peak kWh, time-of-day affinity). Aggregates evidence over all detected events.

**Detects:** EV (fast/slow), immersion heater, shower, washing machine, dishwasher, oven.

**Key output:** `likely_present=True` when ≥4 events match an appliance with mean confidence ≥ 0.55.

**Run:** `python -m smart_meter.tier1.disaggregation`

## S04 — Heat Pump Suitability

Scores each household's suitability for an air-source heat pump replacement of their gas boiler, including payback and NPV calculations.

**How it works:** Separates heating demand from base load (hot water) using summer gas consumption. Models heat pump COP at each day's outdoor temperature. Computes annual running cost under two flow temperature scenarios (optimistic 45°C, conservative 55°C). Applies £7,500 BUS grant to payback calculation.

**Key output:** Four suitability flags plus `viable=True` if payback ≤ 15 years and NPV > 0.

**Run:** `python -m smart_meter.tier1.heat_pump`
```

- [ ] **Step 3: Commit**

```bash
git add docs/requirements.md docs/tier1.md
git commit -m "docs: add requirements and tier1 service documentation"
```

---

## Task 11: Streamlit app

**Files:**
- Create: `app.py`

The new `app.py` imports only Tier 1 modules. It is a simplified version of the original `smart_meter/app.py`, retaining the four service tabs and dropping all Tier 2+ imports.

- [ ] **Step 1: Create app.py**

```python
import sys
import os
import json

import streamlit as st

sys.path.insert(0, "src")

from smart_meter.core.config import (
    METERS, METER_META, ELEC_METERS,
    GAS_RATE_P_KWH, ELEC_RATE_P_KWH, SEG_RATE_P_KWH,
    SOLAR_METERS,
)
import smart_meter.tier1.tariff as s01
import smart_meter.tier1.battery as s02
import smart_meter.tier1.disaggregation as s03
import smart_meter.tier1.heat_pump as s04

st.set_page_config(page_title="Smart Meter — Tier 1", layout="wide")
st.title("Smart Meter Analytics — Tier 1")

meter_ids = sorted(METERS.keys())
selected_meter = st.sidebar.selectbox("Meter", meter_ids, format_func=lambda m: f"M{m}")

tab_tariff, tab_battery, tab_dis, tab_hp = st.tabs([
    "S01 Tariff", "S02 Battery", "S03 Disaggregation", "S04 Heat Pump"
])

with tab_tariff:
    st.header("S01 — Tariff Comparison")
    if st.button("Run S01"):
        with st.spinner("Analysing tariffs..."):
            with open("data/eon_tariffs.json") as f:
                products = json.load(f)
            rows = s01.analyse_meter(selected_meter, products)
        if rows:
            import pandas as pd
            st.dataframe(pd.DataFrame(rows))
        else:
            st.warning("No data for this meter.")

with tab_battery:
    st.header("S02 — Battery Size Optimisation")
    if st.button("Run S02"):
        with st.spinner("Simulating battery..."):
            rows = s02.analyse_meter(selected_meter)
        if rows:
            import pandas as pd
            st.dataframe(pd.DataFrame(rows))
        else:
            st.warning("No data for this meter.")

with tab_dis:
    st.header("S03 — Appliance Disaggregation")
    if st.button("Run S03"):
        with st.spinner("Detecting appliances..."):
            rows = s03.analyse_meter(selected_meter)
        if rows:
            import pandas as pd
            st.dataframe(pd.DataFrame(rows))
        else:
            st.warning("No data for this meter.")

with tab_hp:
    st.header("S04 — Heat Pump Suitability")
    if st.button("Run S04"):
        with st.spinner("Modelling heat pump..."):
            daily_weather = s04._build_daily_weather()
            rows = s04.analyse_meter(selected_meter, daily_weather)
        if rows:
            import pandas as pd
            st.dataframe(pd.DataFrame(rows))
        else:
            st.warning("No data for this meter.")
```

- [ ] **Step 2: Verify the app starts**

```bash
streamlit run app.py --server.headless true &
sleep 3 && curl -s http://localhost:8501 | head -5
```

Expected: HTML response starting with `<!DOCTYPE html>` — app is running.

Kill the process after verifying: `pkill -f "streamlit run"`

- [ ] **Step 3: Run full test suite one final time**

```bash
pytest tests/ -v --tb=short
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "feat: add Streamlit dashboard with Tier 1 service tabs"
```

---

## Self-Review Checklist

After completing all tasks, verify:

- [ ] `pytest tests/ -v` passes with zero failures
- [ ] `python -c "from smart_meter.tier1 import lib, tariff, battery, disaggregation, heat_pump"` imports cleanly
- [ ] `python -c "from smart_meter.core import config, battery_simulator, weather"` imports cleanly
- [ ] `docs/requirements.md` section 1.2 (live data) exists and is clearly marked as future scope
- [ ] Tier 2–4 `__init__.py` stubs exist with placeholder comments
- [ ] No references to `tier2_lib`, `tier3_lib`, or `sys.path.insert` remain in any ported file

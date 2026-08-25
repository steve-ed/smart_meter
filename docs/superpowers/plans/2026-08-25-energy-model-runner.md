# Energy Model Runner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `py/simulation_runner.py` — a top-level runner that wires occupancy, appliance, solar, and forward thermal simulation into a single `run_simulation()` call returning a `SimulationResult`.

**Architecture:** Three tasks build the module in layers. Task 1 defines dataclasses, timestamp helpers, and `load_weather()`. Task 2 adds `forward_simulate()`, which generates synthetic gas consumption and indoor temperature from first principles (no real gas data required). Task 3 adds `run_simulation()`, which calls all four engines and returns a flat `SimulationResult` keyed by timestamp string matching `data/weather.csv` format (`'YYYY-MM-DD HH:MM'`).

**Tech Stack:** Python 3.12 stdlib (`csv`, `math`, `dataclasses`, `datetime`). Imports from `energy_model`, `home_model` (for `decay_step`), `occupancy_model`, `appliance_model`, `solar_model`.

---

### Task 1: Dataclasses, helpers, and load_weather

**Files:**
- Create: `py/simulation_runner.py`
- Create: `tests/test_simulation_runner.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_simulation_runner.py
import csv
import os
from datetime import date

import pytest
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py"))

from simulation_runner import (
    WeatherSeries,
    SimulationResult,
    _ts,
    _flatten_bool,
    _flatten_float,
    load_weather,
)


def test_ts_formats_midnight():
    assert _ts(date(2024, 1, 15), 0) == "2024-01-15 00:00"


def test_ts_formats_half_past():
    assert _ts(date(2024, 1, 15), 1) == "2024-01-15 00:30"


def test_ts_formats_midday():
    assert _ts(date(2024, 1, 15), 24) == "2024-01-15 12:00"


def test_ts_formats_last_slot():
    assert _ts(date(2024, 1, 15), 47) == "2024-01-15 23:30"


def test_flatten_bool():
    d = date(2024, 1, 1)
    series = {d: [True, False] + [True] * 46}
    result = _flatten_bool(series, [d])
    assert result["2024-01-01 00:00"] is True
    assert result["2024-01-01 00:30"] is False
    assert len(result) == 48


def test_flatten_float():
    d = date(2024, 1, 1)
    series = {d: [0.5] * 48}
    result = _flatten_float(series, [d])
    assert result["2024-01-01 00:00"] == pytest.approx(0.5)
    assert len(result) == 48


def test_load_weather_parses_temp_and_wind(tmp_path):
    csv_path = tmp_path / "weather.csv"
    csv_path.write_text(
        "timestamp,temp_c,wind_speed_ms,is_forecast\n"
        "2024-01-01 00:00,5.0,3.2,0\n"
        "2024-01-01 00:30,4.8,3.0,0\n"
    )
    dates = [date(2024, 1, 1)]
    ws = load_weather(dates, str(csv_path))
    assert ws.outdoor_temp_c["2024-01-01 00:00"] == pytest.approx(5.0)
    assert ws.wind_speed_ms["2024-01-01 00:00"] == pytest.approx(3.2)


def test_load_weather_filters_to_dates(tmp_path):
    csv_path = tmp_path / "weather.csv"
    csv_path.write_text(
        "timestamp,temp_c,wind_speed_ms,is_forecast\n"
        "2024-01-01 00:00,5.0,3.2,0\n"
        "2024-01-02 00:00,6.0,2.0,0\n"
    )
    dates = [date(2024, 1, 1)]
    ws = load_weather(dates, str(csv_path))
    assert "2024-01-01 00:00" in ws.outdoor_temp_c
    assert "2024-01-02 00:00" not in ws.outdoor_temp_c


def test_weather_series_has_expected_fields():
    ws = WeatherSeries(outdoor_temp_c={"ts": 5.0}, wind_speed_ms={"ts": 3.2})
    assert ws.outdoor_temp_c["ts"] == 5.0
    assert ws.wind_speed_ms["ts"] == 3.2
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd py && python -m pytest ../tests/test_simulation_runner.py -v 2>&1 | head -30
```

Expected: `ModuleNotFoundError: No module named 'simulation_runner'`

- [ ] **Step 3: Implement the module skeleton**

```python
# py/simulation_runner.py
"""
Top-level simulation runner.

Wires occupancy, appliance, solar, and forward thermal simulation into
a single run_simulation() call returning a SimulationResult.
"""
import csv
import math
from dataclasses import dataclass
from datetime import date

from energy_model import DwellingParams, derived_quantities
from home_model import decay_step
from occupancy_model import DEFAULT_SCHEDULE, OccupancySchedule, generate_occupancy
from appliance_model import DEFAULT_APPLIANCES, ApplianceParams, generate_electricity_profile
from solar_model import generate_solar_profile


@dataclass
class WeatherSeries:
    outdoor_temp_c: dict[str, float]
    wind_speed_ms: dict[str, float]


@dataclass
class SimulationResult:
    dwelling: DwellingParams
    dates: list[date]
    timestamps: list[str]
    outdoor_temp_c: dict[str, float]
    wind_speed_ms: dict[str, float]
    occupancy: dict[str, bool]
    electricity_kwh: dict[str, float]
    gas_kwh: dict[str, float]
    indoor_temp_c: dict[str, float]
    boiler_on: dict[str, bool]
    solar_kwh: dict[str, float] | None


def _ts(d: date, slot: int) -> str:
    h, m = divmod(slot, 2)
    return f"{d} {h:02d}:{m * 30:02d}"


def _flatten_bool(series: dict[date, list[bool]], dates: list[date]) -> dict[str, bool]:
    out: dict[str, bool] = {}
    for d in dates:
        for slot, val in enumerate(series[d]):
            out[_ts(d, slot)] = val
    return out


def _flatten_float(series: dict[date, list[float]], dates: list[date]) -> dict[str, float]:
    out: dict[str, float] = {}
    for d in dates:
        for slot, val in enumerate(series[d]):
            out[_ts(d, slot)] = val
    return out


def load_weather(dates: list[date], weather_path: str = "data/weather.csv") -> WeatherSeries:
    date_strs = {str(d) for d in dates}
    temp_c: dict[str, float] = {}
    wind_ms: dict[str, float] = {}
    with open(weather_path, newline="") as f:
        for row in csv.DictReader(f):
            ts = row["timestamp"]
            if ts[:10] not in date_strs:
                continue
            try:
                temp_c[ts] = float(row["temp_c"])
                wind_ms[ts] = float(row["wind_speed_ms"])
            except (ValueError, KeyError):
                pass
    return WeatherSeries(outdoor_temp_c=temp_c, wind_speed_ms=wind_ms)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd py && python -m pytest ../tests/test_simulation_runner.py -v
```

Expected: 10 PASSED.

- [ ] **Step 5: Commit**

```bash
git add py/simulation_runner.py tests/test_simulation_runner.py
git commit -m "feat: add simulation_runner dataclasses, helpers, and load_weather"
```

---

### Task 2: forward_simulate

**Files:**
- Modify: `py/simulation_runner.py` (add `_HEATING_MONTHS` constant and `forward_simulate`)
- Modify: `tests/test_simulation_runner.py` (add 7 tests)

- [ ] **Step 1: Write the failing tests**

Add these tests to `tests/test_simulation_runner.py`. Add the import line `from simulation_runner import forward_simulate` alongside the existing imports at the top.

```python
from simulation_runner import forward_simulate
from energy_model import create_dwelling


def _make_weather(dates, temp_c, wind_ms=3.0):
    """Build a WeatherSeries with constant values over all slots for all dates."""
    from simulation_runner import WeatherSeries, _ts
    t = {_ts(d, s): temp_c for d in dates for s in range(48)}
    w = {_ts(d, s): wind_ms for d in dates for s in range(48)}
    return WeatherSeries(outdoor_temp_c=t, wind_speed_ms=w)


def test_forward_simulate_winter_boiler_fires():
    """In January at 5°C outdoor, boiler must fire to maintain setpoint."""
    dp = create_dwelling("1970s-semi")
    dates = [date(2024, 1, 15)]
    weather = _make_weather(dates, temp_c=5.0)
    indoor, gas, boiler = forward_simulate(dp, dates, weather)
    assert any(boiler.values()), "Boiler should fire in January at 5°C"


def test_forward_simulate_summer_no_space_heating():
    """In July at 18°C outdoor, gas equals base_load only on every slot."""
    dp = create_dwelling("1990s-semi")
    dates = [date(2024, 7, 15)]
    weather = _make_weather(dates, temp_c=18.0)
    indoor, gas, boiler = forward_simulate(dp, dates, weather)
    assert not any(boiler.values()), "Boiler should not fire in July"
    for ts, kwh in gas.items():
        assert kwh == pytest.approx(dp.base_load_kwh_per_period)


def test_forward_simulate_gas_at_least_base_load():
    """Winter gas must be >= base_load_kwh_per_period on every slot."""
    dp = create_dwelling("pre-1919-terraced")
    dates = [date(2024, 12, 21)]
    weather = _make_weather(dates, temp_c=2.0)
    indoor, gas, boiler = forward_simulate(dp, dates, weather)
    for ts, kwh in gas.items():
        assert kwh >= dp.base_load_kwh_per_period - 1e-9


def test_forward_simulate_indoor_temp_not_below_outdoor():
    """Indoor temperature must never fall below outdoor temperature."""
    dp = create_dwelling("2015-semi")
    dates = [date(2024, 2, 1)]
    weather = _make_weather(dates, temp_c=-5.0)
    indoor, gas, boiler = forward_simulate(dp, dates, weather)
    for ts, t in indoor.items():
        assert t >= -5.0 - 1e-6, f"Indoor {t:.2f}°C below outdoor -5°C at {ts}"


def test_forward_simulate_indoor_temp_not_above_setpoint():
    """Indoor temperature must not exceed t_setpoint."""
    dp = create_dwelling("1970s-semi")
    dates = [date(2024, 1, 15)]
    weather = _make_weather(dates, temp_c=5.0)
    indoor, gas, boiler = forward_simulate(dp, dates, weather)
    for ts, t in indoor.items():
        assert t <= dp.t_setpoint + 1e-6, f"Indoor {t:.2f}°C exceeds setpoint {dp.t_setpoint}"


def test_forward_simulate_returns_48_slots_per_day():
    dp = create_dwelling("1970s-semi")
    dates = [date(2024, 3, 1), date(2024, 3, 2)]
    weather = _make_weather(dates, temp_c=8.0)
    indoor, gas, boiler = forward_simulate(dp, dates, weather)
    assert len(indoor) == 96
    assert len(gas) == 96
    assert len(boiler) == 96


def test_forward_simulate_reproducible():
    dp = create_dwelling("1990s-semi")
    dates = [date(2024, 1, 10)]
    weather = _make_weather(dates, temp_c=6.0)
    r1_indoor, r1_gas, r1_boiler = forward_simulate(dp, dates, weather)
    r2_indoor, r2_gas, r2_boiler = forward_simulate(dp, dates, weather)
    assert r1_indoor == r2_indoor
    assert r1_gas == r2_gas
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd py && python -m pytest ../tests/test_simulation_runner.py -v -k "forward_simulate" 2>&1 | head -20
```

Expected: `ImportError` — `forward_simulate` not yet defined.

- [ ] **Step 3: Implement forward_simulate**

Add these two items to `py/simulation_runner.py`, immediately after the `load_weather` function:

```python
_HEATING_MONTHS: frozenset[int] = frozenset({10, 11, 12, 1, 2, 3, 4})


def forward_simulate(
    dp: DwellingParams,
    dates: list[date],
    weather: WeatherSeries,
) -> tuple[dict[str, float], dict[str, float], dict[str, bool]]:
    """
    Generate synthetic indoor_temp_c, gas_kwh, boiler_on from dwelling physics.

    Space heating fires when the decayed indoor temperature would fall below
    dp.t_setpoint during heating months (Oct–Apr).  Gas per slot is
    space-heating gas + dp.base_load_kwh_per_period.
    """
    dq = derived_quantities(dp)
    tau = dq["tau_hours"]
    c_wh_per_k = dq["c_wh_per_k"]

    indoor_temp: dict[str, float] = {}
    gas_out: dict[str, float] = {}
    boiler_out: dict[str, bool] = {}

    t_indoor = dp.t_setpoint

    for d in dates:
        in_heating = d.month in _HEATING_MONTHS
        for slot in range(48):
            ts = _ts(d, slot)
            t_out = weather.outdoor_temp_c.get(ts, t_indoor)

            t_decay = decay_step(t_indoor, t_out, tau)

            if in_heating and t_decay < dp.t_setpoint:
                heat_needed_wh = (dp.t_setpoint - t_decay) * c_wh_per_k
                gas_heat_kwh = heat_needed_wh / (dp.heating_efficiency * 1000.0)
                t_indoor = dp.t_setpoint
                boiler_on = True
            else:
                t_indoor = max(t_decay, t_out)
                gas_heat_kwh = 0.0
                boiler_on = False

            indoor_temp[ts] = round(t_indoor, 3)
            gas_out[ts] = gas_heat_kwh + dp.base_load_kwh_per_period
            boiler_out[ts] = boiler_on

    return indoor_temp, gas_out, boiler_out
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd py && python -m pytest ../tests/test_simulation_runner.py -v -k "forward_simulate"
```

Expected: 7 PASSED.

- [ ] **Step 5: Commit**

```bash
git add py/simulation_runner.py tests/test_simulation_runner.py
git commit -m "feat: add forward_simulate — physics-driven gas and indoor temp generation"
```

---

### Task 3: run_simulation

**Files:**
- Modify: `py/simulation_runner.py` (add `run_simulation`)
- Modify: `tests/test_simulation_runner.py` (add 7 tests)

- [ ] **Step 1: Write the failing tests**

Add these tests to `tests/test_simulation_runner.py`. Add `from simulation_runner import run_simulation` to the existing imports, and add `from datetime import timedelta` to the stdlib imports.

```python
from simulation_runner import run_simulation
from occupancy_model import DEFAULT_SCHEDULE
from datetime import timedelta


def _winter_week():
    start = date(2024, 1, 8)  # Monday
    return [start + timedelta(days=i) for i in range(7)]


def _write_weather_csv(tmp_path, dates, temp_c=6.0, wind_ms=3.0):
    rows = ["timestamp,temp_c,wind_speed_ms,is_forecast"]
    for d in dates:
        for slot in range(48):
            h, m = divmod(slot, 2)
            ts = f"{d} {h:02d}:{m * 30:02d}"
            rows.append(f"{ts},{temp_c},{wind_ms},0")
    p = tmp_path / "weather.csv"
    p.write_text("\n".join(rows))
    return str(p)


def test_run_simulation_returns_result(tmp_path):
    dp = create_dwelling("1970s-semi")
    dates = _winter_week()
    result = run_simulation(dp, dates, weather_path=_write_weather_csv(tmp_path, dates))
    assert isinstance(result, SimulationResult)


def test_run_simulation_slot_counts(tmp_path):
    dp = create_dwelling("1990s-semi")
    dates = _winter_week()
    result = run_simulation(dp, dates, weather_path=_write_weather_csv(tmp_path, dates))
    n = len(dates) * 48
    assert len(result.timestamps) == n
    assert len(result.electricity_kwh) == n
    assert len(result.gas_kwh) == n
    assert len(result.indoor_temp_c) == n
    assert len(result.boiler_on) == n


def test_run_simulation_electricity_non_negative(tmp_path):
    dp = create_dwelling("1970s-semi")
    dates = _winter_week()
    result = run_simulation(dp, dates, weather_path=_write_weather_csv(tmp_path, dates))
    assert all(v >= 0.0 for v in result.electricity_kwh.values())


def test_run_simulation_solar_none_when_absent(tmp_path):
    dp = create_dwelling("1970s-semi")  # solar_present=False by default
    dates = _winter_week()
    result = run_simulation(dp, dates, weather_path=_write_weather_csv(tmp_path, dates))
    assert result.solar_kwh is None


def test_run_simulation_solar_present_when_configured(tmp_path):
    dp = create_dwelling("2005-detached", solar_present=True, solar_peak_kw=4.0,
                         sensor_solar_generation=True)
    dates = [date(2020, 6, 15)]  # must match pvgis_year=2020 (cached at data/)
    result = run_simulation(
        dp, dates,
        weather_path=_write_weather_csv(tmp_path, dates, temp_c=18.0),
        pvgis_year=2020, pvgis_cache_dir="data",
    )
    assert result.solar_kwh is not None
    assert len(result.solar_kwh) == 48


def test_run_simulation_occupancy_slot_0_is_true(tmp_path):
    """Slot 0 (00:00) is 'sleep' in the default schedule, which maps to True."""
    dp = create_dwelling("1970s-semi")
    dates = [date(2024, 1, 8)]  # Monday
    result = run_simulation(
        dp, dates,
        schedule=DEFAULT_SCHEDULE,
        weather_path=_write_weather_csv(tmp_path, dates),
    )
    assert result.occupancy["2024-01-08 00:00"] is True


def test_run_simulation_reproducible(tmp_path):
    dp = create_dwelling("1990s-semi")
    dates = _winter_week()
    path = _write_weather_csv(tmp_path, dates)
    r1 = run_simulation(dp, dates, seed=42, weather_path=path)
    r2 = run_simulation(dp, dates, seed=42, weather_path=path)
    assert r1.electricity_kwh == r2.electricity_kwh
    assert r1.gas_kwh == r2.gas_kwh
    assert r1.indoor_temp_c == r2.indoor_temp_c
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd py && python -m pytest ../tests/test_simulation_runner.py -v -k "run_simulation" 2>&1 | head -20
```

Expected: `ImportError` — `run_simulation` not yet defined.

- [ ] **Step 3: Implement run_simulation**

Append to `py/simulation_runner.py`:

```python
def run_simulation(
    dp: DwellingParams,
    dates: list[date],
    schedule: OccupancySchedule = DEFAULT_SCHEDULE,
    appliances: dict[str, ApplianceParams] = DEFAULT_APPLIANCES,
    seed: int = 42,
    lat: float = 53.6,
    lon: float = -1.32,
    pvgis_year: int = 2020,
    weather_path: str = "data/weather.csv",
    pvgis_cache_dir: str = "data",
) -> SimulationResult:
    """
    Run a full synthetic simulation for a dwelling over the given dates.

    Returns a SimulationResult with all series keyed by 'YYYY-MM-DD HH:MM'
    timestamp strings, one per half-hour slot.
    """
    weather = load_weather(dates, weather_path)
    occupancy_by_date = generate_occupancy(schedule, dates, seed=seed)
    elec_by_date = generate_electricity_profile(
        appliances, dates, occupancy_by_date,
        seed=seed, occupant_count=dp.occupant_count,
    )
    indoor_temp, gas, boiler_on = forward_simulate(dp, dates, weather)
    solar_by_date = generate_solar_profile(
        dp, lat=lat, lon=lon, year=pvgis_year, cache_dir=pvgis_cache_dir,
    )

    timestamps = [_ts(d, s) for d in dates for s in range(48)]
    solar_flat = _flatten_float(solar_by_date, dates) if solar_by_date is not None else None

    return SimulationResult(
        dwelling=dp,
        dates=dates,
        timestamps=timestamps,
        outdoor_temp_c=weather.outdoor_temp_c,
        wind_speed_ms=weather.wind_speed_ms,
        occupancy=_flatten_bool(occupancy_by_date, dates),
        electricity_kwh=_flatten_float(elec_by_date, dates),
        gas_kwh=gas,
        indoor_temp_c=indoor_temp,
        boiler_on=boiler_on,
        solar_kwh=solar_flat,
    )
```

- [ ] **Step 4: Run all simulation_runner tests**

```bash
cd py && python -m pytest ../tests/test_simulation_runner.py -v
```

Expected: 24 PASSED. If `test_run_simulation_solar_present_when_configured` fails because the PVGIS cache is absent, decorate it with `@pytest.mark.skip(reason="requires PVGIS cache at data/")` and note the skip in the commit message.

- [ ] **Step 5: Run the full test suite to check for regressions**

```bash
cd py && python -m pytest ../tests/ -v 2>&1 | tail -30
```

Expected: All previously passing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add py/simulation_runner.py tests/test_simulation_runner.py
git commit -m "feat: add run_simulation — top-level synthetic data runner"
```

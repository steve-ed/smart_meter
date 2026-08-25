# Energy Model — Synthetic Data Engines — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add three synthetic data engine modules (`occupancy_model.py`, `appliance_model.py`, `solar_model.py`) that generate deterministic half-hourly ground truth signals from a `DwellingParams` instance.

**Architecture:** Each module is self-contained with a public dataclass, a default constant, and one or two generator functions. `appliance_model` depends on `occupancy_model` (for slot filtering); `solar_model` wraps the existing `solar_profile.get_pvgis_profile`. No changes to existing files.

**Tech Stack:** Python 3.10+, `dataclasses`, `random` (seeded), `math`, `pytest`. PVGIS interface already in `py/solar_profile.py`.

---

## File Map

| File | Status | Responsibility |
|---|---|---|
| `py/occupancy_model.py` | Create | `OccupancySchedule`, `DEFAULT_SCHEDULE`, `generate_occupancy()` |
| `py/appliance_model.py` | Create | `ApplianceParams`, `DEFAULT_APPLIANCES`, `generate_appliance_signal()`, `generate_electricity_profile()` |
| `py/solar_model.py` | Create | `generate_solar_profile()` — thin wrapper over `solar_profile.get_pvgis_profile` |
| `tests/test_occupancy_model.py` | Create | Tests for occupancy module |
| `tests/test_appliance_model.py` | Create | Tests for appliance module |
| `tests/test_solar_model.py` | Create | Tests for solar module |
| `py/energy_model.py` | Read-only | `DwellingParams`, `create_dwelling` — imported by `solar_model` |
| `py/solar_profile.py` | Read-only | `get_pvgis_profile` — called by `solar_model` |
| `tests/conftest.py` | Read-only | Adds `py/` to `sys.path`; no changes needed |

---

## Slot index reference

Half-hour slot 0 = 00:00–00:30, slot 1 = 00:30–01:00, …, slot 47 = 23:30–00:00.  
Slot `n` starts at hour `n // 2`, minute `(n % 2) * 30`.

---

## Task 1: Occupancy model

**Files:**
- Create: `py/occupancy_model.py`
- Create: `tests/test_occupancy_model.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_occupancy_model.py
import pytest
from datetime import date, timedelta
from occupancy_model import OccupancySchedule, DEFAULT_SCHEDULE, generate_occupancy


def test_occupancy_schedule_stores_fields():
    s = OccupancySchedule(weekday=["home"] * 48, weekend=["away"] * 48)
    assert s.weekday[0] == "home"
    assert s.weekend[0] == "away"


def test_default_schedule_weekday_length():
    assert len(DEFAULT_SCHEDULE.weekday) == 48
    assert len(DEFAULT_SCHEDULE.weekend) == 48


def test_default_schedule_weekday_away_period():
    # 08:30 = slot 17; 17:00 = slot 34
    assert DEFAULT_SCHEDULE.weekday[17] == "away"
    assert DEFAULT_SCHEDULE.weekday[34] == "away"


def test_default_schedule_weekday_evening_home():
    # 17:30 = slot 35
    assert DEFAULT_SCHEDULE.weekday[35] == "home"


def test_default_schedule_weekend_all_home_or_sleep():
    assert all(s in ("home", "sleep") for s in DEFAULT_SCHEDULE.weekend)


def test_generate_occupancy_weekday_away_slots_false():
    monday = date(2020, 1, 6)  # weekday() == 0
    occ = generate_occupancy(DEFAULT_SCHEDULE, [monday])
    assert occ[monday][17] is False  # 08:30 away
    assert occ[monday][34] is False  # 17:00 away


def test_generate_occupancy_weekday_home_and_sleep_true():
    monday = date(2020, 1, 6)
    occ = generate_occupancy(DEFAULT_SCHEDULE, [monday])
    assert occ[monday][0] is True    # 00:00 sleep
    assert occ[monday][35] is True   # 17:30 home


def test_generate_occupancy_weekend_all_true():
    saturday = date(2020, 1, 4)  # weekday() == 5
    occ = generate_occupancy(DEFAULT_SCHEDULE, [saturday])
    assert all(occ[saturday])


def test_generate_occupancy_returns_48_bools_per_date():
    dates = [date(2020, 1, 6), date(2020, 1, 7)]
    occ = generate_occupancy(DEFAULT_SCHEDULE, dates)
    for d in dates:
        assert len(occ[d]) == 48
        assert all(isinstance(v, bool) for v in occ[d])


def test_generate_occupancy_reproducible():
    dates = [date(2020, 1, 6)]
    assert (generate_occupancy(DEFAULT_SCHEDULE, dates, seed=42) ==
            generate_occupancy(DEFAULT_SCHEDULE, dates, seed=42))


def test_generate_occupancy_weekday_home_fraction_within_2pp():
    """Home fraction in generated signal must match schedule within ±2pp."""
    schedule_home_count = sum(
        1 for s in DEFAULT_SCHEDULE.weekday if s in ("home", "sleep")
    )
    schedule_fraction = schedule_home_count / 48

    weekdays = [date(2020, 1, 6) + timedelta(days=i) for i in range(5)]
    occ = generate_occupancy(DEFAULT_SCHEDULE, weekdays)
    for d in weekdays:
        actual = sum(occ[d]) / 48
        assert abs(actual - schedule_fraction) <= 0.02
```

- [ ] **Step 2: Run to verify all tests fail**

```
cd smart_meter
python -m pytest tests/test_occupancy_model.py -v
```

Expected: `ModuleNotFoundError: No module named 'occupancy_model'`

- [ ] **Step 3: Implement `py/occupancy_model.py`**

```python
from dataclasses import dataclass
from datetime import date


@dataclass
class OccupancySchedule:
    weekday: list[str]  # length 48; each element 'home', 'away', or 'sleep'
    weekend: list[str]  # length 48


def _default_weekday() -> list[str]:
    schedule = []
    for slot in range(48):
        if slot < 14:     # 00:00–06:30  sleep
            schedule.append("sleep")
        elif slot < 17:   # 07:00–08:00  home (getting ready)
            schedule.append("home")
        elif slot < 35:   # 08:30–17:00  away
            schedule.append("away")
        elif slot < 46:   # 17:30–22:30  home
            schedule.append("home")
        else:             # 23:00–23:30  sleep
            schedule.append("sleep")
    return schedule


def _default_weekend() -> list[str]:
    schedule = []
    for slot in range(48):
        if slot < 16:     # 00:00–07:30  sleep
            schedule.append("sleep")
        elif slot < 46:   # 08:00–22:30  home
            schedule.append("home")
        else:             # 23:00–23:30  sleep
            schedule.append("sleep")
    return schedule


DEFAULT_SCHEDULE = OccupancySchedule(
    weekday=_default_weekday(),
    weekend=_default_weekend(),
)


def generate_occupancy(
    schedule: OccupancySchedule,
    dates: list[date],
    seed: int = 42,
) -> dict[date, list[bool]]:
    """
    Generate deterministic binary (home/away) half-hourly occupancy signal.

    'home' and 'sleep' both map to True (occupant present in dwelling);
    'away' maps to False. Weekend = weekday() >= 5.

    Returns dict[date, list[48 bool]].
    """
    result: dict[date, list[bool]] = {}
    for d in dates:
        template = schedule.weekend if d.weekday() >= 5 else schedule.weekday
        result[d] = [s in ("home", "sleep") for s in template]
    return result
```

- [ ] **Step 4: Run tests to verify all pass**

```
python -m pytest tests/test_occupancy_model.py -v
```

Expected: 11 passed

- [ ] **Step 5: Commit**

```bash
git add py/occupancy_model.py tests/test_occupancy_model.py
git commit -m "feat: add occupancy_model with OccupancySchedule and generate_occupancy"
```

---

## Task 2: Appliance data structures

**Files:**
- Create: `py/appliance_model.py` (data structures only — generators added in Task 3)
- Create: `tests/test_appliance_model.py` (structure tests only — fidelity tests added in Task 3)

- [ ] **Step 1: Write failing tests for data structures**

```python
# tests/test_appliance_model.py
import pytest
from datetime import date, timedelta
from appliance_model import (
    ApplianceParams,
    DEFAULT_APPLIANCES,
    generate_appliance_signal,
    generate_electricity_profile,
)


def test_appliance_params_stores_all_fields():
    p = ApplianceParams(
        rated_power_w=2500.0,
        event_duration_min=3.0,
        daily_frequency=6.0,
        seasonal_factor=1.1,
        occupancy_correlated=True,
        scales_with_occupants=False,
    )
    assert p.rated_power_w == 2500.0
    assert p.event_duration_min == 3.0
    assert p.daily_frequency == 6.0
    assert p.seasonal_factor == 1.1
    assert p.occupancy_correlated is True
    assert p.scales_with_occupants is False


def test_appliance_params_defaults():
    p = ApplianceParams(rated_power_w=100.0, event_duration_min=15.0, daily_frequency=48.0)
    assert p.seasonal_factor == 1.0
    assert p.occupancy_correlated is True
    assert p.scales_with_occupants is False


def test_default_appliances_has_all_required():
    required = {
        "water_heater", "fridge", "cooker", "kettle",
        "washing_machine", "dryer", "shower",
    }
    assert required.issubset(DEFAULT_APPLIANCES.keys())


def test_fridge_not_occupancy_correlated():
    assert DEFAULT_APPLIANCES["fridge"].occupancy_correlated is False


def test_fridge_seasonal_factor_above_one():
    assert DEFAULT_APPLIANCES["fridge"].seasonal_factor > 1.0


def test_shower_scales_with_occupants():
    assert DEFAULT_APPLIANCES["shower"].scales_with_occupants is True


def test_shower_rated_power_ge_7000w():
    assert DEFAULT_APPLIANCES["shower"].rated_power_w >= 7000.0


def test_all_daily_frequencies_positive():
    for name, params in DEFAULT_APPLIANCES.items():
        assert params.daily_frequency > 0, f"{name}.daily_frequency must be > 0"


def test_all_rated_powers_positive():
    for name, params in DEFAULT_APPLIANCES.items():
        assert params.rated_power_w > 0, f"{name}.rated_power_w must be > 0"
```

- [ ] **Step 2: Run to verify tests fail**

```
python -m pytest tests/test_appliance_model.py::test_appliance_params_stores_all_fields -v
```

Expected: `ModuleNotFoundError: No module named 'appliance_model'`

- [ ] **Step 3: Implement the data structures in `py/appliance_model.py`**

```python
import math
import random
from dataclasses import dataclass
from datetime import date

_SUMMER_MONTHS: frozenset[int] = frozenset({6, 7, 8})


@dataclass
class ApplianceParams:
    rated_power_w: float          # watts at rated load
    event_duration_min: float     # minutes per event
    daily_frequency: float        # events per day (per occupant if scales_with_occupants)
    seasonal_factor: float = 1.0  # multiplier on daily_frequency for summer (Jun–Aug)
    occupancy_correlated: bool = True    # events only during home/sleep slots
    scales_with_occupants: bool = False  # multiply daily_frequency by occupant_count


DEFAULT_APPLIANCES: dict[str, ApplianceParams] = {
    "water_heater": ApplianceParams(
        rated_power_w=2500.0,
        event_duration_min=30.0,
        daily_frequency=3.0,
    ),
    "fridge": ApplianceParams(
        rated_power_w=150.0,
        event_duration_min=15.0,   # ~50% duty cycle (15 min on, 15 min off)
        daily_frequency=48.0,      # one cycle per half-hour slot
        seasonal_factor=1.1,       # summer +10%
        occupancy_correlated=False,
    ),
    "cooker": ApplianceParams(
        rated_power_w=2500.0,
        event_duration_min=45.0,
        daily_frequency=1.5,
    ),
    "kettle": ApplianceParams(
        rated_power_w=2500.0,
        event_duration_min=3.0,
        daily_frequency=6.0,
    ),
    "washing_machine": ApplianceParams(
        rated_power_w=2000.0,
        event_duration_min=75.0,
        daily_frequency=0.7,
    ),
    "dryer": ApplianceParams(
        rated_power_w=3000.0,
        event_duration_min=52.0,
        daily_frequency=0.4,
    ),
    "shower": ApplianceParams(
        rated_power_w=9000.0,
        event_duration_min=7.0,
        daily_frequency=1.0,       # per occupant
        scales_with_occupants=True,
    ),
}


def generate_appliance_signal(
    appliance_id: str,
    params: ApplianceParams,
    dates: list[date],
    occupancy: dict[date, list[bool]],
    seed: int = 42,
    occupant_count: int = 2,
) -> dict[date, list[float]]:
    raise NotImplementedError


def generate_electricity_profile(
    appliances: dict[str, ApplianceParams],
    dates: list[date],
    occupancy: dict[date, list[bool]],
    seed: int = 42,
    occupant_count: int = 2,
) -> dict[date, list[float]]:
    raise NotImplementedError
```

- [ ] **Step 4: Run structure tests to verify they pass**

```
python -m pytest tests/test_appliance_model.py -k "not generate" -v
```

Expected: 9 passed (structure tests only; generator tests will not run yet)

- [ ] **Step 5: Commit**

```bash
git add py/appliance_model.py tests/test_appliance_model.py
git commit -m "feat: add ApplianceParams dataclass and DEFAULT_APPLIANCES"
```

---

## Task 3: Appliance signal generators

**Files:**
- Modify: `py/appliance_model.py` — implement `generate_appliance_signal` and `generate_electricity_profile`
- Modify: `tests/test_appliance_model.py` — add fidelity tests

- [ ] **Step 1: Add fidelity tests to `tests/test_appliance_model.py`**

Append these tests to the existing file:

```python
def test_generate_appliance_signal_structure():
    dates = [date(2020, 1, 1)]
    occupancy = {date(2020, 1, 1): [True] * 48}
    result = generate_appliance_signal(
        "kettle", DEFAULT_APPLIANCES["kettle"], dates, occupancy
    )
    assert isinstance(result, dict)
    assert dates[0] in result
    assert len(result[dates[0]]) == 48
    assert all(v >= 0.0 for v in result[dates[0]])


def test_fridge_daily_energy_fidelity():
    """Fridge: energy distributed evenly → exact match expected daily energy."""
    params = DEFAULT_APPLIANCES["fridge"]
    # 150/1000 × 15/60 × 48 = 1.8 kWh/day (January, no seasonal uplift)
    expected = params.rated_power_w / 1000.0 * params.event_duration_min / 60.0 * params.daily_frequency

    dates = [date(2020, 1, i) for i in range(1, 8)]
    occupancy = {d: [True] * 48 for d in dates}
    result = generate_appliance_signal("fridge", params, dates, occupancy)

    avg_daily = sum(sum(result[d]) for d in dates) / len(dates)
    assert avg_daily == pytest.approx(expected, rel=0.01)


def test_fridge_summer_energy_uplift():
    """Fridge summer energy must be ~10% above winter energy."""
    params = DEFAULT_APPLIANCES["fridge"]
    winter = [date(2020, 1, i) for i in range(1, 8)]
    summer = [date(2020, 7, i) for i in range(1, 8)]
    occ = {d: [True] * 48 for d in winter + summer}

    win_result = generate_appliance_signal("fridge", params, winter, occ)
    sum_result = generate_appliance_signal("fridge", params, summer, occ)

    win_avg = sum(sum(win_result[d]) for d in winter) / 7
    sum_avg = sum(sum(sum_result[d]) for d in summer) / 7
    assert sum_avg == pytest.approx(win_avg * params.seasonal_factor, rel=0.01)


def test_kettle_daily_energy_fidelity():
    """Kettle average daily energy within ±10% over 7 days."""
    params = DEFAULT_APPLIANCES["kettle"]
    # 2500/1000 × 3/60 × 6 = 0.75 kWh/day
    expected = params.rated_power_w / 1000.0 * params.event_duration_min / 60.0 * params.daily_frequency

    dates = [date(2020, 1, i) for i in range(1, 8)]
    occupancy = {d: [True] * 48 for d in dates}
    result = generate_appliance_signal("kettle", params, dates, occupancy, seed=42)

    avg_daily = sum(sum(result[d]) for d in dates) / len(dates)
    assert avg_daily == pytest.approx(expected, rel=0.10)


def test_washing_machine_average_energy_fidelity():
    """Washing machine average daily energy within ±10% over 14 days."""
    params = DEFAULT_APPLIANCES["washing_machine"]
    # 2000/1000 × 75/60 × 0.7 = 1.75 kWh/day
    expected = params.rated_power_w / 1000.0 * params.event_duration_min / 60.0 * params.daily_frequency

    dates = [date(2020, 1, i) for i in range(1, 15)]
    occupancy = {d: [True] * 48 for d in dates}
    result = generate_appliance_signal("washing_machine", params, dates, occupancy, seed=42)

    avg_daily = sum(sum(result[d]) for d in dates) / len(dates)
    assert avg_daily == pytest.approx(expected, rel=0.10)


def test_shower_scales_with_occupant_count():
    """Shower energy with 4 occupants must be approx double that with 2."""
    params = DEFAULT_APPLIANCES["shower"]
    dates = [date(2020, 1, i) for i in range(1, 15)]
    occupancy = {d: [True] * 48 for d in dates}

    result_2 = generate_appliance_signal("shower", params, dates, occupancy, seed=42, occupant_count=2)
    result_4 = generate_appliance_signal("shower", params, dates, occupancy, seed=42, occupant_count=4)

    total_2 = sum(sum(result_2[d]) for d in dates)
    total_4 = sum(sum(result_4[d]) for d in dates)
    assert total_4 == pytest.approx(total_2 * 2, rel=0.10)


def test_occupancy_correlated_events_only_in_home_slots():
    """For an occupancy-correlated appliance, all energy must be in home slots."""
    dates = [date(2020, 1, 6)]  # Monday
    # Only slots 10–20 are home; rest away
    home_slots = set(range(10, 21))
    occ = {dates[0]: [i in home_slots for i in range(48)]}

    result = generate_appliance_signal(
        "kettle", DEFAULT_APPLIANCES["kettle"], dates, occ, seed=42
    )
    for i, v in enumerate(result[dates[0]]):
        if i not in home_slots:
            assert v == 0.0, f"Slot {i} should be 0 (not home), got {v}"


def test_generate_electricity_profile_structure():
    dates = [date(2020, 1, 1)]
    occupancy = {dates[0]: [True] * 48}
    profile = generate_electricity_profile(DEFAULT_APPLIANCES, dates, occupancy)

    assert dates[0] in profile
    assert len(profile[dates[0]]) == 48
    assert all(v >= 0.0 for v in profile[dates[0]])


def test_generate_electricity_profile_total_energy_fidelity():
    """Total profile daily energy must be within ±10% of sum of individual expected energies."""
    dates = [date(2020, 1, i) for i in range(1, 8)]  # 7 January days
    occupancy = {d: [True] * 48 for d in dates}

    profile = generate_electricity_profile(DEFAULT_APPLIANCES, dates, occupancy)

    # Expected: sum of rated_power × duration × frequency for all appliances
    # Shower: 2 occupants × 1 event × 9000W × 7/60 = 2.1 kWh/day
    expected_per_day = sum(
        params.rated_power_w / 1000.0
        * params.event_duration_min / 60.0
        * params.daily_frequency
        * (2 if params.scales_with_occupants else 1)
        for params in DEFAULT_APPLIANCES.values()
    )
    avg_actual = sum(sum(profile[d]) for d in dates) / len(dates)
    assert avg_actual == pytest.approx(expected_per_day, rel=0.10)
```

- [ ] **Step 2: Run to verify new tests fail**

```
python -m pytest tests/test_appliance_model.py -k "generate" -v
```

Expected: all new tests FAIL with `NotImplementedError`

- [ ] **Step 3: Implement `generate_appliance_signal` and `generate_electricity_profile`**

Replace the two stub functions in `py/appliance_model.py` with:

```python
def generate_appliance_signal(
    appliance_id: str,
    params: ApplianceParams,
    dates: list[date],
    occupancy: dict[date, list[bool]],
    seed: int = 42,
    occupant_count: int = 2,
) -> dict[date, list[float]]:
    """
    Generate half-hourly energy (kWh) for one appliance over the given dates.

    Events are placed using a seeded RNG for reproducibility. If
    params.occupancy_correlated is True, events are restricted to slots
    where the occupant is home. For high-frequency appliances (n_events >=
    len(available)), energy is distributed evenly across available slots
    rather than placed as discrete events.

    Returns dict[date, list[48 float]] — kWh per half-hour.
    """
    rng = random.Random(seed)
    result: dict[date, list[float]] = {}
    event_slots = max(1, math.ceil(params.event_duration_min / 30.0))
    energy_per_event = params.rated_power_w / 1000.0 * params.event_duration_min / 60.0
    energy_per_slot = energy_per_event / event_slots

    for d in dates:
        slots = [0.0] * 48
        factor = params.seasonal_factor if d.month in _SUMMER_MONTHS else 1.0
        freq = params.daily_frequency * factor
        if params.scales_with_occupants:
            freq *= occupant_count

        occ = occupancy.get(d, [True] * 48)
        available = [i for i in range(48) if not params.occupancy_correlated or occ[i]]

        if not available:
            result[d] = slots
            continue

        n_whole = int(freq)
        n_events = n_whole + (1 if rng.random() < (freq - n_whole) else 0)

        if n_events >= len(available):
            # High-frequency appliance (e.g. fridge): distribute total energy evenly.
            total_energy = energy_per_event * freq
            per_slot = total_energy / len(available)
            for i in available:
                slots[i] += per_slot
        else:
            max_start = 48 - event_slots
            for _ in range(n_events):
                valid = [s for s in available if s <= max_start]
                start = rng.choice(valid if valid else available)
                for k in range(event_slots):
                    if start + k < 48:
                        slots[start + k] += energy_per_slot

        result[d] = slots

    return result


def generate_electricity_profile(
    appliances: dict[str, ApplianceParams],
    dates: list[date],
    occupancy: dict[date, list[bool]],
    seed: int = 42,
    occupant_count: int = 2,
) -> dict[date, list[float]]:
    """
    Generate half-hourly total electricity (kWh) as the superposition of all appliances.

    Each appliance receives a unique derived seed so their events are placed
    independently while remaining fully reproducible.

    Returns dict[date, list[48 float]] — kWh per half-hour.
    """
    result: dict[date, list[float]] = {d: [0.0] * 48 for d in dates}
    for appliance_id, params in appliances.items():
        appliance_seed = hash((seed, appliance_id)) & 0x7FFF_FFFF
        signal = generate_appliance_signal(
            appliance_id, params, dates, occupancy,
            seed=appliance_seed, occupant_count=occupant_count,
        )
        for d in dates:
            for i in range(48):
                result[d][i] += signal[d][i]
    return result
```

- [ ] **Step 4: Run all appliance tests**

```
python -m pytest tests/test_appliance_model.py -v
```

Expected: all tests pass

- [ ] **Step 5: Commit**

```bash
git add py/appliance_model.py tests/test_appliance_model.py
git commit -m "feat: implement generate_appliance_signal and generate_electricity_profile"
```

---

## Task 4: Solar model

**Files:**
- Create: `py/solar_model.py`
- Create: `tests/test_solar_model.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_solar_model.py
import pytest
from datetime import date, timedelta
from unittest.mock import patch
from solar_model import generate_solar_profile
from energy_model import create_dwelling


def _uniform_pvgis(kwh_per_slot: float, year: int = 2020) -> dict:
    """Return a PVGIS profile where every slot of every day has kwh_per_slot."""
    start = date(year, 1, 1)
    days = 366 if year % 4 == 0 else 365
    return {start + timedelta(days=i): [kwh_per_slot] * 48 for i in range(days)}


def test_generate_solar_profile_returns_none_when_no_solar():
    p = create_dwelling("1970s-semi")  # solar_present=False by default
    result = generate_solar_profile(p, lat=53.6, lon=-1.32)
    assert result is None


def test_generate_solar_profile_returns_dict_when_solar_present(tmp_path):
    mock_profile = {date(2020, 6, 1): [0.5] * 48}
    with patch("solar_model.get_pvgis_profile", return_value=mock_profile):
        p = create_dwelling(
            "2005-detached",
            solar_present=True,
            solar_peak_kw=4.0,
            solar_performance_ratio=0.8,
        )
        result = generate_solar_profile(p, lat=53.6, lon=-1.32)

    assert result is not None
    assert date(2020, 6, 1) in result
    assert len(result[date(2020, 6, 1)]) == 48


def test_generate_solar_profile_scales_by_peak_kw():
    """Each slot must equal pvgis_slot × peak_kw × performance_ratio."""
    mock_profile = {date(2020, 6, 1): [0.5] * 48}
    with patch("solar_model.get_pvgis_profile", return_value=mock_profile):
        p = create_dwelling(
            "2005-detached",
            solar_present=True,
            solar_peak_kw=4.0,
            solar_performance_ratio=1.0,
        )
        result = generate_solar_profile(p, lat=53.6, lon=-1.32)

    # 0.5 × 4.0 × 1.0 = 2.0 kWh per slot
    assert result[date(2020, 6, 1)][0] == pytest.approx(2.0)


def test_generate_solar_profile_scales_by_performance_ratio():
    mock_profile = {date(2020, 6, 1): [0.5] * 48}
    with patch("solar_model.get_pvgis_profile", return_value=mock_profile):
        p = create_dwelling(
            "2005-detached",
            solar_present=True,
            solar_peak_kw=1.0,
            solar_performance_ratio=0.75,
        )
        result = generate_solar_profile(p, lat=53.6, lon=-1.32)

    # 0.5 × 1.0 × 0.75 = 0.375 kWh per slot
    assert result[date(2020, 6, 1)][0] == pytest.approx(0.375)


def test_generate_solar_profile_uses_dwelling_tilt_and_azimuth():
    """generate_solar_profile must pass solar_tilt_deg and solar_azimuth_deg to PVGIS."""
    mock_profile = {date(2020, 6, 1): [0.1] * 48}
    with patch("solar_model.get_pvgis_profile", return_value=mock_profile) as mock_pvgis:
        p = create_dwelling(
            "2005-detached",
            solar_present=True,
            solar_peak_kw=3.0,
            solar_tilt_deg=30.0,
            solar_azimuth_deg=160.0,
            solar_performance_ratio=0.8,
        )
        generate_solar_profile(p, lat=53.6, lon=-1.32)

    call_kwargs = mock_pvgis.call_args.kwargs
    assert call_kwargs["tilt"] == pytest.approx(30.0)
    assert call_kwargs["azimuth"] == pytest.approx(160.0)


def test_generate_solar_profile_annual_fidelity():
    """Annual yield must be within ±5% of pvgis_annual × peak_kw × PR."""
    # Uniform PVGIS profile totalling 900 kWh/kWp/yr over 366 days (2020 is a leap year)
    kwh_per_slot = 900.0 / 366.0 / 48.0
    mock_profile = _uniform_pvgis(kwh_per_slot, year=2020)

    with patch("solar_model.get_pvgis_profile", return_value=mock_profile):
        p = create_dwelling(
            "2005-detached",
            solar_present=True,
            solar_peak_kw=3.5,
            solar_performance_ratio=0.8,
        )
        result = generate_solar_profile(p, lat=53.6, lon=-1.32)

    annual = sum(sum(slots) for slots in result.values())
    expected = 900.0 * 3.5 * 0.8  # 2520 kWh/yr
    assert annual == pytest.approx(expected, rel=0.05)


def test_generate_solar_profile_non_negative():
    mock_profile = {date(2020, 6, 1): [0.0, 0.5, 1.0, 0.0] + [0.0] * 44}
    with patch("solar_model.get_pvgis_profile", return_value=mock_profile):
        p = create_dwelling(
            "2005-detached",
            solar_present=True,
            solar_peak_kw=4.0,
            solar_performance_ratio=0.8,
        )
        result = generate_solar_profile(p, lat=53.6, lon=-1.32)

    assert all(v >= 0.0 for v in result[date(2020, 6, 1)])
```

- [ ] **Step 2: Run to verify all tests fail**

```
python -m pytest tests/test_solar_model.py -v
```

Expected: `ModuleNotFoundError: No module named 'solar_model'`

- [ ] **Step 3: Implement `py/solar_model.py`**

```python
from datetime import date
from energy_model import DwellingParams
from solar_profile import get_pvgis_profile


def generate_solar_profile(
    p: DwellingParams,
    lat: float,
    lon: float,
    year: int = 2020,
    cache_dir: str = "data",
) -> dict[date, list[float]] | None:
    """
    Generate half-hourly solar generation (kWh) for a dwelling.

    Returns None if p.solar_present is False.

    Calls get_pvgis_profile with the dwelling's tilt and azimuth, then
    scales each slot by peak_kw × performance_ratio.

    Returns dict[date, list[48 float]] — kWh per half-hour.
    """
    if not p.solar_present:
        return None

    pvgis = get_pvgis_profile(
        lat=lat,
        lon=lon,
        tilt=p.solar_tilt_deg,
        azimuth=p.solar_azimuth_deg,
        year=year,
        cache_dir=cache_dir,
    )
    scale = p.solar_peak_kw * p.solar_performance_ratio
    return {d: [s * scale for s in slots] for d, slots in pvgis.items()}
```

- [ ] **Step 4: Run all solar tests**

```
python -m pytest tests/test_solar_model.py -v
```

Expected: all 8 tests pass

- [ ] **Step 5: Run the full test suite to check for regressions**

```
python -m pytest tests/ -v --tb=short
```

Expected: all existing tests still pass; new tests all pass

- [ ] **Step 6: Commit**

```bash
git add py/solar_model.py tests/test_solar_model.py
git commit -m "feat: add solar_model with generate_solar_profile wrapping PVGIS"
```

---

## Spec Self-Review

### 1. Spec coverage

| Spec requirement | Task covering it |
|---|---|
| `OccupancySchedule` with weekday/weekend | Task 1 |
| `DEFAULT_SCHEDULE` (named default) | Task 1 |
| `generate_occupancy()` — deterministic, seed param | Task 1 |
| Occupancy fidelity: ±2pp fraction per week | Task 1 — `test_generate_occupancy_weekday_home_fraction_within_2pp` |
| `ApplianceParams` with all 6 fields | Task 2 |
| `DEFAULT_APPLIANCES` — all 7 named appliances | Task 2 |
| `occupancy_correlated` enforcement | Task 3 — `test_occupancy_correlated_events_only_in_home_slots` |
| `scales_with_occupants` for shower | Tasks 2+3 |
| Seasonal uplift (summer ×factor) | Task 3 — `test_fridge_summer_energy_uplift` |
| Appliance fidelity: ±10% daily energy | Task 3 — fridge, kettle, washing machine tests |
| `generate_electricity_profile()` superposition | Task 3 — `test_generate_electricity_profile_total_energy_fidelity` |
| `generate_solar_profile()` None when no solar | Task 4 |
| Uses DwellingParams tilt/azimuth | Task 4 — `test_generate_solar_profile_uses_dwelling_tilt_and_azimuth` |
| Solar fidelity: annual within ±5% | Task 4 — `test_generate_solar_profile_annual_fidelity` |
| Reproducibility (same seed = same output) | Task 1 — `test_generate_occupancy_reproducible`; Task 3 (deterministic by construction) |

### 2. Placeholder scan

No TBD, TODO, or "implement later" in any step. All code blocks are complete.

### 3. Type consistency

- `OccupancySchedule.weekday/weekend`: `list[str]` — consistent across Task 1 tests and implementation.
- `generate_occupancy` returns `dict[date, list[bool]]` — consistent with Task 3's `occupancy` parameter type.
- `ApplianceParams` fields: same names/types in dataclass, DEFAULT_APPLIANCES, and test assertions.
- `generate_appliance_signal` signature: `(appliance_id: str, params: ApplianceParams, dates: list[date], occupancy: dict[date, list[bool]], seed: int, occupant_count: int) -> dict[date, list[float]]` — used consistently in Task 3 tests.
- `generate_electricity_profile` signature consistent with Task 3 tests.
- `generate_solar_profile` returns `dict[date, list[float]] | None` — None branch tested in Task 4.

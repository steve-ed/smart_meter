# Energy Model — Core Infrastructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create `py/energy_model.py` as the single source of truth for the parameterised dwelling model, then refactor `py/home_model.py` to use it — preserving backward-compatibility for `tier4_analysis.py` and `app.py`.

**Architecture:** `energy_model.py` defines `DwellingParams` (dataclass), `derived_quantities()`, five named archetypes, `create_dwelling()` with override support, and `validate_sensor_tier()`. `home_model.py` imports from it, replacing its internal `DWELLING_PARAMS` dict and `build_dwelling()` with the new API while keeping public symbols available for existing callers.

**Tech Stack:** Python 3.13, dataclasses stdlib, pytest 8.x. No new dependencies.

---

## File Map

| Action | File | Responsibility |
|---|---|---|
| Create | `py/energy_model.py` | DwellingParams, derived_quantities, ARCHETYPES, create_dwelling, validate_sensor_tier |
| Create | `tests/test_energy_model.py` | Unit tests for all energy_model.py components |
| Modify | `py/home_model.py` | Replace DWELLING_PARAMS + build_dwelling with energy_model imports; keep backward-compat symbols |

All tests run from the project root: `pytest tests/test_energy_model.py -v`

---

## Task 1: DwellingParams dataclass

**Files:**
- Create: `py/energy_model.py`
- Create: `tests/test_energy_model.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_energy_model.py`:

```python
import pytest
from energy_model import DwellingParams


def test_dwelling_params_requires_geometry():
    """All four geometry fields are required — no defaults."""
    with pytest.raises(TypeError):
        DwellingParams()


def test_dwelling_params_geometry_stored():
    p = DwellingParams(
        total_floor_area_m2=85.0,
        storey_height_m=2.4,
        window_area_m2=14.0,
        door_area_m2=3.6,
    )
    assert p.total_floor_area_m2 == 85.0
    assert p.storey_height_m == 2.4
    assert p.window_area_m2 == 14.0
    assert p.door_area_m2 == 3.6


def test_dwelling_params_defaults():
    p = DwellingParams(
        total_floor_area_m2=85.0,
        storey_height_m=2.4,
        window_area_m2=14.0,
        door_area_m2=3.6,
    )
    assert p.plan_aspect_ratio == 1.0
    assert p.heating_fuel == "gas"
    assert p.heating_system_type == "boiler"
    assert p.heating_efficiency == 0.89
    assert p.heat_threshold_kwh == 0.15
    assert p.t_setpoint == 20.0
    assert p.solar_present is False
    assert p.battery_present is False
    assert p.sensor_elec_meter is True
    assert p.sensor_gas_meter is True
    assert p.sensor_outdoor_temp is False
    assert p.sensor_indoor_temp is False
    assert p.occupancy_source == "synthetic"
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/test_energy_model.py -v
```

Expected: `ModuleNotFoundError: No module named 'energy_model'`

- [ ] **Step 3: Create py/energy_model.py with DwellingParams**

```python
"""
Energy model — parameterised dwelling for value-added feature assessment.

Defines DwellingParams (full parameter catalogue), archetype presets,
derived quantities (HTC, τ), and sensor tier validation.

See docs/superpowers/specs/2026-08-25-energy-model-design.md for requirements.
"""

from dataclasses import dataclass


@dataclass
class DwellingParams:
    # ---- Geometry (required) ----
    total_floor_area_m2: float
    storey_height_m: float
    window_area_m2: float
    door_area_m2: float
    plan_aspect_ratio: float = 1.0

    # ---- Fabric ----
    u_wall: float = 0.0
    u_roof: float = 0.0
    u_floor: float = 0.0
    u_window: float = 0.0
    u_door: float = 0.0
    y_value: float = 0.09
    q50: float = 8.0
    kappa: float = 160.0

    # ---- Heating system ----
    heating_fuel: str = "gas"
    heating_system_type: str = "boiler"
    heating_efficiency: float = 0.89
    heat_threshold_kwh: float = 0.15
    t_setpoint: float = 20.0
    base_load_kwh_per_period: float = 0.08

    # ---- Solar (optional) ----
    solar_present: bool = False
    solar_peak_kw: float = 0.0
    solar_azimuth_deg: float = 180.0
    solar_tilt_deg: float = 35.0
    solar_performance_ratio: float = 0.8
    solar_export_metered: bool = False

    # ---- Battery (optional) ----
    battery_present: bool = False
    battery_capacity_kwh: float = 0.0
    battery_rte: float = 0.9
    battery_charge_rate_kw: float = 0.0
    battery_discharge_rate_kw: float = 0.0

    # ---- Sensors ----
    sensor_elec_meter: bool = True
    sensor_gas_meter: bool = True
    sensor_outdoor_temp: bool = False
    sensor_wind_speed: bool = False
    sensor_occupancy: bool = False
    sensor_indoor_temp: bool = False
    sensor_solar_generation: bool = False
    sensor_battery_state: bool = False

    # ---- Occupancy ----
    occupant_count: int = 2
    occupancy_source: str = "synthetic"

    # ---- Metadata ----
    label: str = ""
    archetype_id: str = ""
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_energy_model.py -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add py/energy_model.py tests/test_energy_model.py
git commit -m "feat: add DwellingParams dataclass to energy_model.py"
```

---

## Task 2: derived_quantities()

**Files:**
- Modify: `py/energy_model.py` (add function)
- Modify: `tests/test_energy_model.py` (add tests)

- [ ] **Step 1: Write failing tests**

Append to `tests/test_energy_model.py`:

```python
from energy_model import derived_quantities


def test_derived_quantities_returns_htc_and_tau():
    p = DwellingParams(
        total_floor_area_m2=85.0, storey_height_m=2.4,
        window_area_m2=14.0, door_area_m2=3.6,
        u_wall=0.60, u_roof=0.35, u_floor=0.70,
        u_window=2.80, u_door=3.00,
        y_value=0.15, q50=10.0, kappa=160,
    )
    d = derived_quantities(p)
    assert "htc" in d
    assert "tau_hours" in d
    assert "c_wh_per_k" in d
    assert d["htc"] > 0
    assert d["tau_hours"] > 0


def test_derived_quantities_meter1_htc():
    """1970s semi HTC ≈ 225 W/K per worked example in docs/home_model.md."""
    p = DwellingParams(
        total_floor_area_m2=85.0, storey_height_m=2.4,
        window_area_m2=14.0, door_area_m2=3.6,
        u_wall=0.60, u_roof=0.35, u_floor=0.70,
        u_window=2.80, u_door=3.00,
        y_value=0.15, q50=10.0, kappa=160,
    )
    d = derived_quantities(p)
    assert abs(d["htc"] - 225.1) < 2.0


def test_derived_quantities_square_plan_envelope():
    """Square plan (aspect=1): envelope = 4×side×h×2 + 2×footprint."""
    p = DwellingParams(
        total_floor_area_m2=80.0, storey_height_m=2.4,
        window_area_m2=0.0, door_area_m2=0.0,
    )
    d = derived_quantities(p)
    footprint = 40.0
    side = footprint ** 0.5
    expected_envelope = 4 * side * 2.4 * 2 + footprint + footprint
    assert abs(d["envelope_area_m2"] - expected_envelope) < 0.01


def test_derived_quantities_aspect_ratio_increases_envelope():
    """2:1 rectangle has more perimeter than square of same floor area."""
    base = dict(
        total_floor_area_m2=80.0, storey_height_m=2.4,
        window_area_m2=0.0, door_area_m2=0.0,
    )
    d1 = derived_quantities(DwellingParams(**base, plan_aspect_ratio=1.0))
    d2 = derived_quantities(DwellingParams(**base, plan_aspect_ratio=2.0))
    assert d2["envelope_area_m2"] > d1["envelope_area_m2"]


def test_derived_quantities_c_wh_per_k():
    p = DwellingParams(
        total_floor_area_m2=85.0, storey_height_m=2.4,
        window_area_m2=14.0, door_area_m2=3.6,
        kappa=160,
    )
    d = derived_quantities(p)
    assert abs(d["c_wh_per_k"] - 160 * 85.0) < 0.01


def test_derived_quantities_tau_equals_c_over_htc():
    p = DwellingParams(
        total_floor_area_m2=85.0, storey_height_m=2.4,
        window_area_m2=14.0, door_area_m2=3.6,
        u_wall=0.60, u_roof=0.35, u_floor=0.70,
        u_window=2.80, u_door=3.00,
        y_value=0.15, q50=10.0, kappa=160,
    )
    d = derived_quantities(p)
    assert abs(d["tau_hours"] - d["c_wh_per_k"] / d["htc"]) < 0.001
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_energy_model.py -v -k "derived"
```

Expected: `ImportError` — `derived_quantities` not yet defined

- [ ] **Step 3: Add derived_quantities() to py/energy_model.py**

Add after the `DwellingParams` class:

```python
_C_AIR = 0.33  # Wh/m³K — volumetric heat capacity of air


def derived_quantities(p: DwellingParams) -> dict:
    """Compute HTC, tau, and envelope geometry from a DwellingParams instance."""
    footprint = p.total_floor_area_m2 / 2.0
    aspect = p.plan_aspect_ratio
    width = (footprint / aspect) ** 0.5
    length = width * aspect
    perimeter = 2.0 * (length + width)
    wall_gross = perimeter * p.storey_height_m * 2.0
    wall_net = wall_gross - p.window_area_m2 - p.door_area_m2
    roof_area = footprint
    floor_area = footprint
    envelope_area = wall_gross + roof_area + floor_area
    volume = p.total_floor_area_m2 * p.storey_height_m

    fabric_htc = (
        p.u_wall   * wall_net +
        p.u_roof   * roof_area +
        p.u_floor  * floor_area +
        p.u_window * p.window_area_m2 +
        p.u_door   * p.door_area_m2
    )
    bridging_htc = p.y_value * envelope_area
    leakage_50pa = p.q50 * envelope_area
    n50 = leakage_50pa / volume
    ach_natural = n50 / 20.0
    ventilation_htc = _C_AIR * ach_natural * volume

    htc = fabric_htc + bridging_htc + ventilation_htc
    c_wh_per_k = p.kappa * p.total_floor_area_m2
    tau_hours = c_wh_per_k / htc

    return {
        "footprint_m2":     footprint,
        "wall_gross_m2":    wall_gross,
        "wall_net_m2":      wall_net,
        "roof_area_m2":     roof_area,
        "floor_area_m2":    floor_area,
        "envelope_area_m2": envelope_area,
        "volume_m3":        volume,
        "ach_natural":      ach_natural,
        "fabric_htc":       fabric_htc,
        "bridging_htc":     bridging_htc,
        "ventilation_htc":  ventilation_htc,
        "htc":              htc,
        "c_wh_per_k":       c_wh_per_k,
        "tau_hours":        tau_hours,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_energy_model.py -v -k "derived"
```

Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add py/energy_model.py tests/test_energy_model.py
git commit -m "feat: add derived_quantities() to energy_model.py"
```

---

## Task 3: Archetype registry and create_dwelling()

**Files:**
- Modify: `py/energy_model.py`
- Modify: `tests/test_energy_model.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_energy_model.py`:

```python
from energy_model import ARCHETYPES, create_dwelling


def test_all_five_archetypes_present():
    expected = {
        "pre-1919-terraced", "1970s-semi", "1990s-semi",
        "2005-detached", "2015-semi",
    }
    assert expected == set(ARCHETYPES)


def test_create_dwelling_returns_dwelling_params():
    p = create_dwelling("1970s-semi")
    assert isinstance(p, DwellingParams)


def test_create_dwelling_archetype_id_set():
    p = create_dwelling("1970s-semi")
    assert p.archetype_id == "1970s-semi"


def test_create_dwelling_unknown_raises():
    with pytest.raises(ValueError, match="Unknown archetype"):
        create_dwelling("nonexistent")


def test_create_dwelling_override_single_param():
    p = create_dwelling("1970s-semi", u_wall=0.20)
    assert p.u_wall == 0.20
    assert p.u_roof == 0.35  # unchanged from archetype


def test_create_dwelling_override_does_not_mutate_archetype():
    create_dwelling("1970s-semi", u_wall=0.20)
    p2 = create_dwelling("1970s-semi")
    assert p2.u_wall == 0.60  # original value restored


def test_create_dwelling_all_archetypes_valid():
    """Every archetype produces a DwellingParams with positive floor area."""
    for arch_id in ARCHETYPES:
        p = create_dwelling(arch_id)
        assert p.total_floor_area_m2 > 0, f"{arch_id} has zero floor area"
        assert p.htc_computable(), f"{arch_id} missing fabric params"


def test_archetype_meter1_matches_home_model_params():
    """1970s-semi must match the values in DWELLING_PARAMS[1] from home_model.py."""
    p = create_dwelling("1970s-semi")
    assert p.total_floor_area_m2 == 85.0
    assert p.u_wall == 0.60
    assert p.q50 == 10.0
    assert p.kappa == 160


def test_archetype_meter4_pre1919():
    p = create_dwelling("pre-1919-terraced")
    assert p.u_wall == 1.70
    assert p.storey_height_m == 2.7
    assert p.kappa == 220
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_energy_model.py -v -k "archetype or create_dwelling or five"
```

Expected: `ImportError` — `ARCHETYPES` and `create_dwelling` not yet defined. Also `AttributeError` on `htc_computable`.

- [ ] **Step 3: Add htc_computable() method to DwellingParams**

Add this method inside the `DwellingParams` class (after all field definitions):

```python
    def htc_computable(self) -> bool:
        """True when all U-values and q50 are set (non-zero)."""
        return all([
            self.u_wall, self.u_roof, self.u_floor,
            self.u_window, self.u_door, self.q50,
        ])
```

- [ ] **Step 4: Add ARCHETYPES dict and create_dwelling() to py/energy_model.py**

Add after `derived_quantities()`:

```python
ARCHETYPES: dict[str, dict] = {
    "pre-1919-terraced": {
        "archetype_id":        "pre-1919-terraced",
        "label":               "Pre-1919 solid brick terraced",
        "total_floor_area_m2": 75.0,
        "storey_height_m":     2.7,
        "window_area_m2":      10.0,
        "door_area_m2":         3.0,
        "u_wall":               1.70,
        "u_roof":               0.16,
        "u_floor":              0.70,
        "u_window":             1.80,
        "u_door":               2.00,
        "y_value":              0.15,
        "q50":                 14.0,
        "kappa":              220,
        "sensor_elec_meter":   True,
        "sensor_gas_meter":    True,
        "sensor_outdoor_temp": True,
        "sensor_wind_speed":   True,
    },
    "1970s-semi": {
        "archetype_id":        "1970s-semi",
        "label":               "1970s semi, unimproved",
        "total_floor_area_m2": 85.0,
        "storey_height_m":     2.4,
        "window_area_m2":      14.0,
        "door_area_m2":         3.6,
        "u_wall":               0.60,
        "u_roof":               0.35,
        "u_floor":              0.70,
        "u_window":             2.80,
        "u_door":               3.00,
        "y_value":              0.15,
        "q50":                 10.0,
        "kappa":              160,
        "sensor_elec_meter":   True,
        "sensor_gas_meter":    True,
        "sensor_outdoor_temp": True,
        "sensor_wind_speed":   True,
    },
    "1990s-semi": {
        "archetype_id":        "1990s-semi",
        "label":               "1990s semi, partial upgrade",
        "total_floor_area_m2": 90.0,
        "storey_height_m":     2.4,
        "window_area_m2":      16.0,
        "door_area_m2":         3.6,
        "u_wall":               0.60,
        "u_roof":               0.16,
        "u_floor":              0.45,
        "u_window":             1.80,
        "u_door":               1.80,
        "y_value":              0.09,
        "q50":                  8.0,
        "kappa":              160,
        "sensor_elec_meter":   True,
        "sensor_gas_meter":    True,
        "sensor_outdoor_temp": True,
        "sensor_wind_speed":   True,
    },
    "2005-detached": {
        "archetype_id":        "2005-detached",
        "label":               "2005 detached, Part L 2002",
        "total_floor_area_m2": 130.0,
        "storey_height_m":     2.4,
        "window_area_m2":      22.0,
        "door_area_m2":         4.0,
        "u_wall":               0.35,
        "u_roof":               0.16,
        "u_floor":              0.25,
        "u_window":             1.60,
        "u_door":               1.40,
        "y_value":              0.08,
        "q50":                  6.0,
        "kappa":              155,
        "sensor_elec_meter":   True,
        "sensor_gas_meter":    True,
        "sensor_outdoor_temp": True,
        "sensor_wind_speed":   True,
        "sensor_indoor_temp":  True,
        "sensor_solar_generation": True,
    },
    "2015-semi": {
        "archetype_id":        "2015-semi",
        "label":               "2015 semi, Part L 2013",
        "total_floor_area_m2": 88.0,
        "storey_height_m":     2.4,
        "window_area_m2":      15.0,
        "door_area_m2":         3.6,
        "u_wall":               0.28,
        "u_roof":               0.13,
        "u_floor":              0.20,
        "u_window":             1.40,
        "u_door":               1.20,
        "y_value":              0.05,
        "q50":                  4.0,
        "kappa":              145,
        "sensor_elec_meter":   True,
        "sensor_gas_meter":    True,
        "sensor_outdoor_temp": True,
        "sensor_wind_speed":   True,
    },
}


def create_dwelling(archetype_id: str, **overrides) -> "DwellingParams":
    """Create a DwellingParams from a named archetype with optional field overrides."""
    if archetype_id not in ARCHETYPES:
        raise ValueError(
            f"Unknown archetype: '{archetype_id}'. "
            f"Valid: {sorted(ARCHETYPES)}"
        )
    params = dict(ARCHETYPES[archetype_id])
    params.update(overrides)
    return DwellingParams(**params)
```

- [ ] **Step 5: Run tests to verify they pass**

```
pytest tests/test_energy_model.py -v -k "archetype or create_dwelling or five"
```

Expected: 9 passed

- [ ] **Step 6: Commit**

```bash
git add py/energy_model.py tests/test_energy_model.py
git commit -m "feat: add archetype registry and create_dwelling() to energy_model.py"
```

---

## Task 4: Sensor tier validation

**Files:**
- Modify: `py/energy_model.py`
- Modify: `tests/test_energy_model.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_energy_model.py`:

```python
from energy_model import validate_sensor_tier


def test_validate_tier1_passes_all_archetypes():
    """All archetypes have elec + gas meter sensors by default."""
    for arch_id in ARCHETYPES:
        p = create_dwelling(arch_id)
        ok, missing = validate_sensor_tier(p, 1)
        assert ok, f"{arch_id} failed tier 1: missing {missing}"


def test_validate_tier2_passes_all_archetypes():
    """All archetypes have outdoor_temp + wind_speed sensors by default."""
    for arch_id in ARCHETYPES:
        p = create_dwelling(arch_id)
        ok, missing = validate_sensor_tier(p, 2)
        assert ok, f"{arch_id} failed tier 2: missing {missing}"


def test_validate_tier4_fails_without_indoor_temp():
    p = create_dwelling("1970s-semi")  # no indoor_temp sensor
    ok, missing = validate_sensor_tier(p, 4)
    assert not ok
    assert "sensor_indoor_temp" in missing


def test_validate_tier4_fails_without_occupancy():
    p = create_dwelling("1970s-semi", sensor_indoor_temp=True)
    ok, missing = validate_sensor_tier(p, 4)
    assert not ok
    assert "sensor_occupancy" in missing


def test_validate_tier4_passes_with_all_sensors():
    p = create_dwelling("1970s-semi",
                        sensor_occupancy=True,
                        sensor_indoor_temp=True)
    ok, missing = validate_sensor_tier(p, 4)
    assert ok, f"Unexpected missing: {missing}"


def test_validate_missing_returns_list():
    p = create_dwelling("1970s-semi")
    ok, missing = validate_sensor_tier(p, 4)
    assert isinstance(missing, list)
    assert len(missing) > 0


def test_validate_tier5_missing_solar_and_battery():
    p = create_dwelling("1970s-semi",
                        sensor_occupancy=True,
                        sensor_indoor_temp=True)
    ok, missing = validate_sensor_tier(p, 5)
    assert not ok
    assert "sensor_solar_generation" in missing
    assert "sensor_battery_state" in missing


def test_validate_unknown_tier_raises():
    p = create_dwelling("1970s-semi")
    with pytest.raises(ValueError, match="Unknown tier"):
        validate_sensor_tier(p, 99)
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_energy_model.py -v -k "validate"
```

Expected: `ImportError` — `validate_sensor_tier` not yet defined

- [ ] **Step 3: Add validate_sensor_tier() to py/energy_model.py**

Add after `create_dwelling()`:

```python
_TIER_SENSORS: dict[int, frozenset] = {
    1: frozenset({
        "sensor_elec_meter", "sensor_gas_meter",
    }),
    2: frozenset({
        "sensor_elec_meter", "sensor_gas_meter",
        "sensor_outdoor_temp", "sensor_wind_speed",
    }),
    3: frozenset({
        "sensor_elec_meter", "sensor_gas_meter",
        "sensor_outdoor_temp", "sensor_wind_speed",
        "sensor_occupancy",
    }),
    4: frozenset({
        "sensor_elec_meter", "sensor_gas_meter",
        "sensor_outdoor_temp", "sensor_wind_speed",
        "sensor_occupancy", "sensor_indoor_temp",
    }),
    5: frozenset({
        "sensor_elec_meter", "sensor_gas_meter",
        "sensor_outdoor_temp", "sensor_wind_speed",
        "sensor_occupancy", "sensor_indoor_temp",
        "sensor_solar_generation", "sensor_battery_state",
    }),
}


def validate_sensor_tier(p: "DwellingParams", tier: int) -> tuple[bool, list[str]]:
    """
    Check whether a dwelling meets the sensor prerequisite for a given tier.

    Returns (ok, missing) where ok is True when all required sensors are
    present and missing is the list of sensor field names that are False.
    """
    if tier not in _TIER_SENSORS:
        raise ValueError(f"Unknown tier {tier}. Valid: {sorted(_TIER_SENSORS)}")
    missing = sorted(s for s in _TIER_SENSORS[tier] if not getattr(p, s))
    return len(missing) == 0, missing
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_energy_model.py -v -k "validate"
```

Expected: 8 passed

- [ ] **Step 5: Run the full test file**

```
pytest tests/test_energy_model.py -v
```

Expected: all tests pass (no failures)

- [ ] **Step 6: Commit**

```bash
git add py/energy_model.py tests/test_energy_model.py
git commit -m "feat: add sensor tier validation to energy_model.py"
```

---

## Task 5: Refactor home_model.py

Replace the internal `DWELLING_PARAMS` dict and `build_dwelling()` with `energy_model.py` imports. Preserve both as public symbols for backward-compatibility with `tier4_analysis.py` and `app.py` which import them directly.

**Files:**
- Modify: `py/home_model.py`

- [ ] **Step 1: Write a backward-compatibility integration test**

Create `tests/test_home_model_compat.py`:

```python
"""
Verify that home_model.py public symbols are unchanged after the energy_model refactor.
tier4_analysis.py and app.py import DWELLING_PARAMS and build_dwelling directly.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'py'))

from home_model import DWELLING_PARAMS, build_dwelling


def test_dwelling_params_has_all_meters():
    """Meters 1-5 must be present (plus 6-15 for completeness)."""
    for m in range(1, 6):
        assert m in DWELLING_PARAMS, f"meter {m} missing from DWELLING_PARAMS"


def test_dwelling_params_meter1_values():
    p = DWELLING_PARAMS[1]
    assert p["total_floor_area_m2"] == 85.0
    assert p["u_wall"] == 0.60
    assert p["q50"] == 10.0
    assert p["label"] == "1970s semi, unimproved"


def test_build_dwelling_returns_htc():
    d = build_dwelling(DWELLING_PARAMS[1])
    assert "htc" in d
    assert d["htc"] > 0


def test_build_dwelling_returns_tau():
    d = build_dwelling(DWELLING_PARAMS[1])
    assert "tau_hours" in d
    assert d["tau_hours"] > 0


def test_build_dwelling_returns_c_wh_k():
    """tier4_analysis.py uses the key 'c_wh_k' (old name)."""
    d = build_dwelling(DWELLING_PARAMS[1])
    assert "c_wh_k" in d
    assert abs(d["c_wh_k"] - 160 * 85.0) < 0.1


def test_build_dwelling_meter1_htc_matches_spec():
    """HTC should be ~225 W/K for meter 1 per docs/home_model.md worked example."""
    d = build_dwelling(DWELLING_PARAMS[1])
    assert abs(d["htc"] - 225.1) < 2.0
```

- [ ] **Step 2: Run the test to verify it passes before refactoring**

```
pytest tests/test_home_model_compat.py -v
```

Expected: 6 passed. This confirms the baseline. If any fail, stop and investigate before proceeding.

- [ ] **Step 3: Add energy_model import and METER_PARAMS to home_model.py**

At the top of `py/home_model.py`, after the existing imports, add:

```python
from energy_model import (
    DwellingParams,
    ARCHETYPES,
    create_dwelling,
    derived_quantities,
)
```

Then replace the `DWELLING_PARAMS` dict (the entire block from line 31 to line 258) with:

```python
# ---------------------------------------------------------------------------
# Dwelling parameters — one DwellingParams per meter
# ---------------------------------------------------------------------------

METER_PARAMS: dict[int, DwellingParams] = {
    1: create_dwelling("1970s-semi"),
    2: create_dwelling("1990s-semi"),
    3: create_dwelling("2005-detached"),
    4: create_dwelling("pre-1919-terraced"),
    5: create_dwelling("2015-semi"),
    # Meters 6-15: era-spanning semis, not named archetypes in the spec
    6: DwellingParams(
        label="1975 semi, pre-1976 regs", archetype_id="",
        total_floor_area_m2=88.0, storey_height_m=2.4,
        window_area_m2=14.0, door_area_m2=3.6,
        u_wall=0.60, u_roof=0.35, u_floor=0.70,
        u_window=2.80, u_door=3.00,
        y_value=0.15, q50=10.0, kappa=170,
        sensor_elec_meter=True, sensor_gas_meter=True,
        sensor_outdoor_temp=True, sensor_wind_speed=True,
    ),
    7: DwellingParams(
        label="1980 semi, 1976 regs", archetype_id="",
        total_floor_area_m2=88.0, storey_height_m=2.4,
        window_area_m2=14.0, door_area_m2=3.6,
        u_wall=0.60, u_roof=0.35, u_floor=0.60,
        u_window=2.80, u_door=2.80,
        y_value=0.15, q50=10.0, kappa=165,
        sensor_elec_meter=True, sensor_gas_meter=True,
        sensor_outdoor_temp=True, sensor_wind_speed=True,
    ),
    8: DwellingParams(
        label="1985 semi, 1985 regs", archetype_id="",
        total_floor_area_m2=88.0, storey_height_m=2.4,
        window_area_m2=14.0, door_area_m2=3.6,
        u_wall=0.60, u_roof=0.25, u_floor=0.45,
        u_window=2.80, u_door=2.80,
        y_value=0.12, q50=9.0, kappa=160,
        sensor_elec_meter=True, sensor_gas_meter=True,
        sensor_outdoor_temp=True, sensor_wind_speed=True,
    ),
    9: DwellingParams(
        label="1990 semi, Part L 1990", archetype_id="",
        total_floor_area_m2=88.0, storey_height_m=2.4,
        window_area_m2=15.0, door_area_m2=3.6,
        u_wall=0.45, u_roof=0.25, u_floor=0.45,
        u_window=2.80, u_door=2.80,
        y_value=0.12, q50=9.0, kappa=160,
        sensor_elec_meter=True, sensor_gas_meter=True,
        sensor_outdoor_temp=True, sensor_wind_speed=True,
    ),
    10: DwellingParams(
        label="1995 semi, Part L 1995", archetype_id="",
        total_floor_area_m2=88.0, storey_height_m=2.4,
        window_area_m2=15.0, door_area_m2=3.6,
        u_wall=0.45, u_roof=0.25, u_floor=0.45,
        u_window=2.80, u_door=2.80,
        y_value=0.10, q50=8.0, kappa=158,
        sensor_elec_meter=True, sensor_gas_meter=True,
        sensor_outdoor_temp=True, sensor_wind_speed=True,
    ),
    11: DwellingParams(
        label="2000 semi, Part L 2000", archetype_id="",
        total_floor_area_m2=88.0, storey_height_m=2.4,
        window_area_m2=15.0, door_area_m2=3.6,
        u_wall=0.35, u_roof=0.16, u_floor=0.25,
        u_window=2.00, u_door=2.00,
        y_value=0.09, q50=7.0, kappa=155,
        sensor_elec_meter=True, sensor_gas_meter=True,
        sensor_outdoor_temp=True, sensor_wind_speed=True,
    ),
    12: DwellingParams(
        label="2005 semi, Part L 2002", archetype_id="",
        total_floor_area_m2=88.0, storey_height_m=2.4,
        window_area_m2=15.0, door_area_m2=3.6,
        u_wall=0.35, u_roof=0.16, u_floor=0.25,
        u_window=1.60, u_door=1.60,
        y_value=0.08, q50=6.0, kappa=150,
        sensor_elec_meter=True, sensor_gas_meter=True,
        sensor_outdoor_temp=True, sensor_wind_speed=True,
    ),
    13: DwellingParams(
        label="2010 semi, Part L 2010", archetype_id="",
        total_floor_area_m2=88.0, storey_height_m=2.4,
        window_area_m2=15.0, door_area_m2=3.6,
        u_wall=0.30, u_roof=0.13, u_floor=0.22,
        u_window=1.60, u_door=1.40,
        y_value=0.07, q50=5.0, kappa=148,
        sensor_elec_meter=True, sensor_gas_meter=True,
        sensor_outdoor_temp=True, sensor_wind_speed=True,
    ),
    14: DwellingParams(
        label="2015 semi, Part L 2013", archetype_id="",
        total_floor_area_m2=88.0, storey_height_m=2.4,
        window_area_m2=15.0, door_area_m2=3.6,
        u_wall=0.28, u_roof=0.13, u_floor=0.20,
        u_window=1.40, u_door=1.20,
        y_value=0.05, q50=4.0, kappa=145,
        sensor_elec_meter=True, sensor_gas_meter=True,
        sensor_outdoor_temp=True, sensor_wind_speed=True,
    ),
    15: DwellingParams(
        label="2020 semi, Part L 2021", archetype_id="",
        total_floor_area_m2=88.0, storey_height_m=2.4,
        window_area_m2=15.0, door_area_m2=3.6,
        u_wall=0.18, u_roof=0.11, u_floor=0.13,
        u_window=1.20, u_door=1.00,
        y_value=0.04, q50=3.0, kappa=140,
        sensor_elec_meter=True, sensor_gas_meter=True,
        sensor_outdoor_temp=True, sensor_wind_speed=True,
    ),
}

# Backward-compatible dict-of-dicts for callers that use DWELLING_PARAMS[n]["param"]
# (tier4_analysis.py, app.py). Do not remove.
from dataclasses import asdict as _asdict
DWELLING_PARAMS: dict[int, dict] = {k: _asdict(v) for k, v in METER_PARAMS.items()}
```

- [ ] **Step 4: Replace build_dwelling() in home_model.py**

Find the existing `build_dwelling(p: dict) -> dict` function and replace it entirely with:

```python
def build_dwelling(p: dict) -> dict:
    """
    Backward-compatible wrapper over derived_quantities().
    Accepts the same dict format as the old DWELLING_PARAMS entries.
    Returns the same keys as the original implementation.
    tier4_analysis.py and app.py use this — do not change the return keys.
    """
    fields = DwellingParams.__dataclass_fields__
    dp = DwellingParams(**{k: v for k, v in p.items() if k in fields})
    d = derived_quantities(dp)
    # Remap to the old key names that callers depend on
    d["c_wh_k"]       = d.pop("c_wh_per_k")
    d["vent_htc"]      = d.pop("ventilation_htc")
    d["envelope_area"] = d.pop("envelope_area_m2")
    d["volume"]        = d.pop("volume_m3")
    d["wall_net"]      = d.pop("wall_net_m2")
    return d
```

- [ ] **Step 5: Update the simulate() and heating_step() signatures**

In `home_model.py`, update `heating_step` to accept `efficiency` and `t_setpoint` as parameters (so the per-dwelling values can be passed in):

```python
def heating_step(t_indoor: float, t_outdoor: float,
                 gas_kwh_heating: float,
                 htc: float, c_wh_k: float,
                 efficiency: float = BOILER_EFFICIENCY,
                 t_setpoint: float = T_SETPOINT) -> float:
    """Heat balance over one half-hour period. Capped at t_setpoint."""
    q_boiler = gas_kwh_heating * efficiency * 1000
    q_loss   = htc * (t_indoor - t_outdoor) * DT_HOURS
    delta_t  = (q_boiler - q_loss) / c_wh_k
    return min(t_indoor + delta_t, t_setpoint)
```

Update `simulate()` to accept and thread through these parameters:

```python
def simulate(periods: list[dict],
             htc: float,
             c_wh_k: float,
             tau: float,
             base_load_kwh: float,
             efficiency: float = BOILER_EFFICIENCY,
             t_setpoint: float = T_SETPOINT,
             heat_threshold_kwh: float = HEAT_THRESHOLD_KWH) -> list[dict]:
    results = []
    t_indoor = t_setpoint

    for p in periods:
        t_out    = p["outdoor_c"]
        gas_kwh  = p["gas_kwh"]
        month    = p["month"]

        in_summer = month in SUMMER_MONTHS
        boiler_on = (not in_summer) and (gas_kwh >= heat_threshold_kwh)

        if boiler_on:
            gas_heat = max(gas_kwh - base_load_kwh, 0.0)
            t_indoor = heating_step(t_indoor, t_out, gas_heat, htc, c_wh_k,
                                    efficiency=efficiency,
                                    t_setpoint=t_setpoint)
        else:
            t_indoor = decay_step(t_indoor, t_out, tau)

        t_indoor = max(t_indoor, t_out)

        results.append({
            "timestamp":    p["timestamp"],
            "period_index": p["period_index"],
            "temp_c":       round(t_indoor, 3),
            "boiler_on":    int(boiler_on),
            "outdoor_c":    round(t_out, 2),
        })

    return results
```

- [ ] **Step 6: Update main() to use METER_PARAMS**

In `main()`, replace:

```python
params  = DWELLING_PARAMS[meter_num]
dwelling = build_dwelling(params)
```

with:

```python
dp       = METER_PARAMS[meter_num]
dwelling = derived_quantities(dp)
# remap c_wh_per_k to c_wh_k for print statements below
dwelling["c_wh_k"] = dwelling["c_wh_per_k"]
dwelling["vent_htc"] = dwelling["ventilation_htc"]
```

Replace the `simulate()` call in `main()`:

```python
results = simulate(periods, dwelling["htc"], dwelling["c_wh_k"],
                   dwelling["tau_hours"], base_load,
                   efficiency=dp.heating_efficiency,
                   t_setpoint=dp.t_setpoint,
                   heat_threshold_kwh=dp.heat_threshold_kwh)
```

Replace the `params["label"]` references in `main()` with `dp.label`.

- [ ] **Step 7: Run backward-compatibility tests**

```
pytest tests/test_home_model_compat.py -v
```

Expected: 6 passed. If any fail, the refactor broke something — check the key mappings in `build_dwelling()`.

- [ ] **Step 8: Run the full test suite**

```
pytest tests/ -v --ignore=tests/__pycache__
```

Expected: all existing tests still pass. The refactor must not regress any test.

- [ ] **Step 9: Commit**

```bash
git add py/home_model.py tests/test_home_model_compat.py
git commit -m "refactor: home_model.py uses energy_model.py; backward-compat preserved"
```

---

## Self-Review

**Spec coverage check:**

| Spec section | Covered by task |
|---|---|
| §2.1 Geometry params | Task 1 — DwellingParams fields |
| §2.2 Fabric params | Task 1 — DwellingParams fields |
| §2.3 Heating system params | Task 1 — DwellingParams fields |
| §2.4 Solar params | Task 1 — DwellingParams fields |
| §2.5 Battery params | Task 1 — DwellingParams fields |
| §2.6 Sensor flags | Task 1 — DwellingParams fields; Task 4 validation |
| §2.7 Occupancy params | Task 1 — DwellingParams fields |
| §2.8 Appliance signatures | **Not in this plan — Plan 2** |
| §2.9 Weather inputs | Not parameterised (file paths only) — no code change needed |
| §3 Archetype presets + overrides | Task 3 |
| §4 Sensor tiers | Task 4 |
| §5 Feature assessment matrix | Documentation only — no code |
| §6.1 Indoor temp ground truth | Existing home_model.py simulation; refactored in Task 5 |
| §6.2 Electricity ground truth | **Plan 2** |
| §6.3 Gas ground truth | Existing home_model.py; refactored in Task 5 |
| §6.4 Solar ground truth | **Plan 2** |
| §6.5 Occupancy ground truth | **Plan 2** |
| §7 Derived quantities | Task 2 |

**Placeholder scan:** No TBDs, no incomplete steps.

**Type consistency check:**
- `DwellingParams` used consistently across all tasks
- `derived_quantities()` returns `c_wh_per_k`; `build_dwelling()` maps to `c_wh_k` — explicitly documented
- `create_dwelling()` return type matches `DwellingParams` — consistent

---

## Follow-on: Plan 2

Plan 2 covers the synthetic data engines not in scope here:
- `py/appliance_model.py` — per-appliance power draw profiles, superposition into synthetic electricity
- `py/occupancy_model.py` — deterministic occupancy from schedule + seed
- `py/solar_model.py` — half-hourly generation from PVGIS data
- Fidelity validation tests for each (§6.2, §6.4, §6.5 of the spec)

import pytest
from energy_model import ARCHETYPES, DwellingParams, create_dwelling, derived_quantities


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

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

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

import pytest
from datetime import date
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
    """Fridge: energy distributed evenly -> exact match expected daily energy."""
    params = DEFAULT_APPLIANCES["fridge"]
    # 150/1000 x 15/60 x 48 = 1.8 kWh/day (January, no seasonal uplift)
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
    """Kettle average daily energy within +-10% over 7 days."""
    params = DEFAULT_APPLIANCES["kettle"]
    # 2500/1000 x 3/60 x 6 = 0.75 kWh/day
    expected = params.rated_power_w / 1000.0 * params.event_duration_min / 60.0 * params.daily_frequency

    dates = [date(2020, 1, i) for i in range(1, 8)]
    occupancy = {d: [True] * 48 for d in dates}
    result = generate_appliance_signal("kettle", params, dates, occupancy, seed=42)

    avg_daily = sum(sum(result[d]) for d in dates) / len(dates)
    assert avg_daily == pytest.approx(expected, rel=0.10)


def test_washing_machine_average_energy_fidelity():
    """Washing machine average daily energy within +-10% over 14 days."""
    params = DEFAULT_APPLIANCES["washing_machine"]
    # 2000/1000 x 75/60 x 0.7 = 1.75 kWh/day
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
    # Only slots 10-20 are home; rest away
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
    """Total profile daily energy must be within +-10% of sum of individual expected energies."""
    dates = [date(2020, 1, i) for i in range(1, 8)]  # 7 January days
    occupancy = {d: [True] * 48 for d in dates}

    profile = generate_electricity_profile(DEFAULT_APPLIANCES, dates, occupancy)

    # Expected: sum of rated_power x duration x frequency for all appliances
    # Shower: 2 occupants x 1 event x 9000W x 7/60 = 2.1 kWh/day
    expected_per_day = sum(
        params.rated_power_w / 1000.0
        * params.event_duration_min / 60.0
        * params.daily_frequency
        * (2 if params.scales_with_occupants else 1)
        for params in DEFAULT_APPLIANCES.values()
    )
    avg_actual = sum(sum(profile[d]) for d in dates) / len(dates)
    assert avg_actual == pytest.approx(expected_per_day, rel=0.10)

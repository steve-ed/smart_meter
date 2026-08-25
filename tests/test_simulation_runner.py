# tests/test_simulation_runner.py
import csv
import os
from datetime import date, timedelta

import pytest
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py"))

from simulation_runner import (
    WeatherSeries,
    SimulationResult,
    DEFAULT_SETPOINT_SCHEDULE,
    _ts,
    _flatten_bool,
    _flatten_float,
    load_weather,
    forward_simulate,
    forward_simulate_two_zone,
    run_simulation,
)
from energy_model import create_dwelling, DwellingParams
from occupancy_model import DEFAULT_SCHEDULE


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


def _make_weather(dates, temp_c, wind_ms=3.0):
    """Build a WeatherSeries with constant values for all slots and all dates."""
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
    assert r1_boiler == r2_boiler


def _winter_week():
    start = date(2024, 1, 8)  # Monday
    return [start + timedelta(days=i) for i in range(7)]


def _write_weather_csv(tmp_path, dates, temp_c=6.0, wind_ms=3.0):
    rows = ["timestamp,temp_c,wind_speed_ms,is_forecast"]
    for d in dates:
        for slot in range(48):
            ts = _ts(d, slot)
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


@pytest.mark.skip(reason="requires PVGIS cache at data/")
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
    assert len(result.solar_kwh) == len(dates) * 48


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


# --- setpoint schedule tests ---

def test_default_setpoint_schedule_length():
    assert len(DEFAULT_SETPOINT_SCHEDULE) == 48


def test_default_setpoint_schedule_setback_during_sleep():
    # slots 0-13 are sleep → 16°C
    assert all(DEFAULT_SETPOINT_SCHEDULE[s] == 16.0 for s in range(14))


def test_default_setpoint_schedule_comfort_during_evening():
    # slots 35-45 are evening home → 20°C
    assert all(DEFAULT_SETPOINT_SCHEDULE[s] == 20.0 for s in range(35, 46))


def test_setpoint_schedule_boiler_off_during_setback_when_warm():
    """During setback slots, boiler must not fire while indoor temp is above the setback setpoint."""
    dp = create_dwelling("1970s-semi", t_setpoint_schedule=DEFAULT_SETPOINT_SCHEDULE)
    dates = [date(2024, 1, 15)]
    weather = _make_weather(dates, temp_c=5.0)
    indoor, gas, boiler = forward_simulate(dp, dates, weather)
    # Setback slots (0-13) have 16°C setpoint — boiler should not fire while indoor > 16°C
    for slot in range(14):
        ts = _ts(dates[0], slot)
        if indoor[ts] > 16.0:
            assert not boiler[ts], f"Slot {slot}: boiler fired at {indoor[ts]:.2f}°C with 16°C setback"


def test_setpoint_schedule_lower_gas_than_flat_setpoint():
    """A setback schedule must consume less gas than a flat 20°C setpoint."""
    dp_flat = create_dwelling("1970s-semi")
    dp_sched = create_dwelling("1970s-semi", t_setpoint_schedule=DEFAULT_SETPOINT_SCHEDULE)
    dates = [date(2024, 1, 15)]
    weather = _make_weather(dates, temp_c=5.0)
    _, gas_flat, _ = forward_simulate(dp_flat, dates, weather)
    _, gas_sched, _ = forward_simulate(dp_sched, dates, weather)
    assert sum(gas_sched.values()) < sum(gas_flat.values())


def test_none_schedule_uses_flat_setpoint():
    """t_setpoint_schedule=None must produce same result as no schedule set."""
    dp1 = create_dwelling("1990s-semi")
    dp2 = create_dwelling("1990s-semi", t_setpoint_schedule=None)
    dates = [date(2024, 1, 10)]
    weather = _make_weather(dates, temp_c=6.0)
    i1, g1, b1 = forward_simulate(dp1, dates, weather)
    i2, g2, b2 = forward_simulate(dp2, dates, weather)
    assert i1 == i2
    assert g1 == g2


# --- boiler_max_kw tests ---

def test_boiler_cap_limits_gas_per_slot():
    """With a 24 kW cap, gas (space heating only) never exceeds 12 kWh per slot."""
    dp = create_dwelling("1970s-semi", boiler_max_kw=24.0,
                         t_setpoint_schedule=DEFAULT_SETPOINT_SCHEDULE)
    dates = [date(2024, 1, 15)]
    weather = _make_weather(dates, temp_c=3.0)
    _, gas, _ = forward_simulate(dp, dates, weather)
    max_gas_per_slot = 24.0 * 0.5 + dp.base_load_kwh_per_period  # cap + base load
    for ts, kwh in gas.items():
        assert kwh <= max_gas_per_slot + 1e-9, f"{ts}: {kwh:.4f} kWh exceeds cap"


def test_boiler_cap_spreads_warmup_over_multiple_slots():
    """With a cap, morning warmup must span more than one slot."""
    dp_capped = create_dwelling("1970s-semi", boiler_max_kw=12.0,
                                t_setpoint_schedule=DEFAULT_SETPOINT_SCHEDULE)
    dates = [date(2024, 1, 15)]
    weather = _make_weather(dates, temp_c=3.0)
    _, gas, boiler = forward_simulate(dp_capped, dates, weather)
    # Morning warmup: slots 14 onward until setpoint reached
    warmup_slots = sum(1 for s in range(14, 20) if boiler[_ts(dates[0], s)])
    assert warmup_slots > 1, "Capped boiler should need more than one slot to warm up"


def test_boiler_cap_zero_matches_uncapped():
    """boiler_max_kw=0.0 must produce identical results to the default (uncapped)."""
    dp1 = create_dwelling("1990s-semi")
    dp2 = create_dwelling("1990s-semi", boiler_max_kw=0.0)
    dates = [date(2024, 1, 10)]
    weather = _make_weather(dates, temp_c=6.0)
    i1, g1, b1 = forward_simulate(dp1, dates, weather)
    i2, g2, b2 = forward_simulate(dp2, dates, weather)
    assert g1 == g2
    assert i1 == i2


def test_boiler_cap_indoor_never_exceeds_setpoint():
    """Even with a cap, indoor temperature must never exceed the active setpoint."""
    dp = create_dwelling("1970s-semi", boiler_max_kw=24.0)
    dates = [date(2024, 1, 15)]
    weather = _make_weather(dates, temp_c=3.0)
    indoor, _, _ = forward_simulate(dp, dates, weather)
    for ts, t in indoor.items():
        assert t <= dp.t_setpoint + 1e-6


# --- internal gains tests ---

def test_internal_gains_reduce_winter_gas():
    """Internal gains from appliances must reduce boiler gas demand."""
    dp = create_dwelling("1970s-semi")
    dates = [date(2024, 1, 15)]
    weather = _make_weather(dates, temp_c=3.0)
    _, gas_no_gains, _ = forward_simulate(dp, dates, weather, internal_gains=None)
    gains = {_ts(dates[0], s): 0.5 for s in range(48)}  # 0.5 kWh/slot constant gain
    _, gas_with_gains, _ = forward_simulate(dp, dates, weather, internal_gains=gains)
    assert sum(gas_with_gains.values()) < sum(gas_no_gains.values())


def test_internal_gains_none_matches_no_gains():
    """internal_gains=None must produce identical results to gains of zero."""
    dp = create_dwelling("1990s-semi")
    dates = [date(2024, 1, 10)]
    weather = _make_weather(dates, temp_c=6.0)
    i1, g1, b1 = forward_simulate(dp, dates, weather, internal_gains=None)
    zero_gains = {_ts(dates[0], s): 0.0 for s in range(48)}
    i2, g2, b2 = forward_simulate(dp, dates, weather, internal_gains=zero_gains)
    assert g1 == g2
    assert i1 == i2


def test_internal_gains_raise_summer_indoor_temp():
    """In summer, internal gains should raise indoor temperature above outdoor."""
    dp = create_dwelling("1990s-semi")
    dates = [date(2024, 7, 15)]
    weather = _make_weather(dates, temp_c=18.0)
    indoor_no_gains, _, _ = forward_simulate(dp, dates, weather, internal_gains=None)
    gains = {_ts(dates[0], s): 0.3 for s in range(48)}
    indoor_with_gains, _, _ = forward_simulate(dp, dates, weather, internal_gains=gains)
    avg_no = sum(indoor_no_gains.values()) / 48
    avg_with = sum(indoor_with_gains.values()) / 48
    assert avg_with > avg_no


def test_internal_gains_fraction_zero_passes_no_gains(tmp_path):
    """internal_gains_fraction=0.0 in run_simulation must pass gains=None to forward_simulate."""
    dp = create_dwelling("1970s-semi", internal_gains_fraction=0.0)
    dp_default = create_dwelling("1970s-semi", internal_gains_fraction=0.0)
    dates = _winter_week()
    path = _write_weather_csv(tmp_path, dates)
    result = run_simulation(dp, dates, weather_path=path)
    # With zero gains fraction, gas must equal the no-gains forward_simulate result
    weather_obj = WeatherSeries(
        outdoor_temp_c={_ts(d, s): 6.0 for d in dates for s in range(48)},
        wind_speed_ms={_ts(d, s): 3.0 for d in dates for s in range(48)},
    )
    _, gas_ref, _ = forward_simulate(dp_default, dates, weather_obj, internal_gains=None)
    assert result.gas_kwh == gas_ref


# --- two-zone model tests ---

def _two_zone_dp(**overrides):
    defaults = dict(zone2_floor_area_m2=20.0, inter_zone_conductance_w_per_k=30.0, zone2_t_initial=18.0)
    defaults.update(overrides)
    return create_dwelling("1970s-semi", **defaults)


def test_two_zone_returns_four_series():
    dp = _two_zone_dp()
    dates = [date(2024, 1, 15)]
    weather = _make_weather(dates, temp_c=5.0)
    z1, gas, boiler, z2 = forward_simulate_two_zone(dp, dates, weather)
    assert len(z1) == 48
    assert len(z2) == 48
    assert len(gas) == 48
    assert len(boiler) == 48


def test_two_zone_z2_warmer_than_outdoor_in_winter():
    """Zone 2 receives heat from zone 1 — must stay above outdoor temp."""
    dp = _two_zone_dp()
    dates = [date(2024, 1, 15)]
    weather = _make_weather(dates, temp_c=2.0)
    _, _, _, z2 = forward_simulate_two_zone(dp, dates, weather)
    assert all(t >= 2.0 - 1e-6 for t in z2.values())


def test_two_zone_z2_cooler_than_z1_in_winter():
    """Unheated bedroom must stay below heated living zone in winter."""
    dp = _two_zone_dp(t_setpoint_schedule=DEFAULT_SETPOINT_SCHEDULE)
    dates = [date(2024, 1, 15)]
    weather = _make_weather(dates, temp_c=3.0)
    z1, _, _, z2 = forward_simulate_two_zone(dp, dates, weather)
    avg_z1 = sum(z1.values()) / len(z1)
    avg_z2 = sum(z2.values()) / len(z2)
    assert avg_z2 < avg_z1


def test_two_zone_z1_boiler_fires_in_winter():
    dp = _two_zone_dp()
    dates = [date(2024, 1, 15)]
    weather = _make_weather(dates, temp_c=5.0)
    _, _, boiler, _ = forward_simulate_two_zone(dp, dates, weather)
    assert any(boiler.values())


def test_two_zone_gas_at_least_base_load():
    dp = _two_zone_dp()
    dates = [date(2024, 1, 15)]
    weather = _make_weather(dates, temp_c=5.0)
    _, gas, _, _ = forward_simulate_two_zone(dp, dates, weather)
    for kwh in gas.values():
        assert kwh >= dp.base_load_kwh_per_period - 1e-9


def test_two_zone_z2_approaches_z1_with_high_conductance():
    """High inter-zone conductance should equalise zone temperatures."""
    dp_tight = _two_zone_dp(inter_zone_conductance_w_per_k=500.0)
    dp_loose = _two_zone_dp(inter_zone_conductance_w_per_k=5.0)
    dates = [date(2024, 1, 15)]
    weather = _make_weather(dates, temp_c=3.0)
    z1_t, _, _, z2_t = forward_simulate_two_zone(dp_tight, dates, weather)
    z1_l, _, _, z2_l = forward_simulate_two_zone(dp_loose, dates, weather)
    gap_tight = sum(abs(z1_t[ts] - z2_t[ts]) for ts in z1_t) / 48
    gap_loose = sum(abs(z1_l[ts] - z2_l[ts]) for ts in z1_l) / 48
    assert gap_tight < gap_loose


def test_run_simulation_two_zone_populates_z2(tmp_path):
    dp = _two_zone_dp()
    dates = _winter_week()
    result = run_simulation(dp, dates, weather_path=_write_weather_csv(tmp_path, dates))
    assert result.indoor_temp_c_z2 is not None
    assert len(result.indoor_temp_c_z2) == len(dates) * 48


def test_run_simulation_single_zone_z2_is_none(tmp_path):
    dp = create_dwelling("1970s-semi")   # zone2_floor_area_m2 defaults to 0.0
    dates = _winter_week()
    result = run_simulation(dp, dates, weather_path=_write_weather_csv(tmp_path, dates))
    assert result.indoor_temp_c_z2 is None


def test_invalid_schedule_length_raises():
    """A schedule with wrong length must raise ValueError."""
    dp = create_dwelling("1970s-semi", t_setpoint_schedule=[20.0] * 24)
    dates = [date(2024, 1, 15)]
    weather = _make_weather(dates, temp_c=5.0)
    with pytest.raises(ValueError, match="48"):
        forward_simulate(dp, dates, weather)

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
    _ts,
    _flatten_bool,
    _flatten_float,
    load_weather,
    forward_simulate,
    run_simulation,
)
from energy_model import create_dwelling
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

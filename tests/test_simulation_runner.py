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

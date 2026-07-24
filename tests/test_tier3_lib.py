import pytest
from tier3_lib import _daily_mean_temp


def _make_weather_rows(dates_temps):
    """dates_temps: list of (date_str, temp_c) — one row per date."""
    rows = []
    for date_str, temp in dates_temps:
        rows.append({
            "timestamp": f"{date_str} 00:00",
            "temp_c": temp,
            "wind_speed_ms": 2.0,
            "is_forecast": 0,
        })
    return rows


def test_daily_mean_temp_single_reading_per_day():
    rows = _make_weather_rows([("2025-01-01", 5.0), ("2025-01-02", 10.0)])
    result = _daily_mean_temp(rows)
    assert result == {"2025-01-01": 5.0, "2025-01-02": 10.0}


def test_daily_mean_temp_multiple_readings_averaged():
    rows = [
        {"timestamp": "2025-01-01 00:00", "temp_c": 4.0, "wind_speed_ms": 0.0, "is_forecast": 0},
        {"timestamp": "2025-01-01 00:30", "temp_c": 6.0, "wind_speed_ms": 0.0, "is_forecast": 0},
    ]
    result = _daily_mean_temp(rows)
    assert result["2025-01-01"] == pytest.approx(5.0)


def test_daily_mean_temp_empty_returns_empty():
    assert _daily_mean_temp([]) == {}


def test_load_labeled_days_is_callable():
    from tier3_lib import load_labeled_days
    assert callable(load_labeled_days)

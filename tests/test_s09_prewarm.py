import pytest
from s09_prewarm import (
    extract_boiler_start,
    is_smart_thermostat_present,
    recommend_start_time,
)


def test_extract_boiler_start_finds_first():
    periods = [(0, 0.0), (2, 0.0), (4, 0.20), (6, 0.25), (14, 0.30)]
    assert extract_boiler_start(periods) == 4

def test_extract_boiler_start_none_if_below_threshold():
    periods = [(0, 0.05), (4, 0.10), (8, 0.05)]
    assert extract_boiler_start(periods) is None

def test_extract_boiler_start_only_morning_window():
    periods = [(26, 0.50), (4, 0.05)]
    assert extract_boiler_start(periods) is None


def test_smart_thermostat_detected_low_variance():
    obs = [(14, t) for t in range(0, 20)]
    assert is_smart_thermostat_present(obs) is True

def test_smart_thermostat_not_detected_high_variance():
    import random
    random.seed(42)
    obs = [(14 + random.randint(-5, 5), t) for t in range(0, 20)]
    assert is_smart_thermostat_present(obs) is False

def test_smart_thermostat_insufficient_obs():
    obs = [(14, t) for t in range(0, 10)]
    assert is_smart_thermostat_present(obs) is False


def test_recommend_clamps_before_target():
    result = recommend_start_time(
        forecast_temp=5.0, slope=-1.0, intercept=20.0,
        target_period=14, r_squared=0.80,
    )
    assert result["recommended_start_period"] <= 13

def test_recommend_insufficient_r2():
    result = recommend_start_time(
        forecast_temp=5.0, slope=-1.0, intercept=20.0,
        target_period=14, r_squared=0.30,
    )
    assert result["recommendation"] is None
    assert "insufficient_pattern" in result["reason"]

def test_recommend_clamped_to_zero():
    result = recommend_start_time(
        forecast_temp=-10.0, slope=-2.0, intercept=5.0,
        target_period=14, r_squared=0.90,
    )
    assert result["recommended_start_period"] >= 0

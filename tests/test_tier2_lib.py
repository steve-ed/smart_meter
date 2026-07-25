import pytest
from tier2_lib import (
    daily_hdd, period_hdd, effective_temp,
    fit_hdd_regression,
    period_to_time, time_to_period,
    UK_BENCHMARKS, benchmark_percentile,
)


# --- daily_hdd ---

def test_daily_hdd_cold():
    assert daily_hdd(5.0) == pytest.approx(10.5)

def test_daily_hdd_warm():
    assert daily_hdd(20.0) == 0.0

def test_daily_hdd_at_base():
    assert daily_hdd(15.5) == 0.0


# --- period_hdd ---

def test_period_hdd_cold():
    assert period_hdd(5.0) == pytest.approx(10.5 / 48)

def test_period_hdd_warm():
    assert period_hdd(20.0) == 0.0


# --- effective_temp ---

def test_effective_temp_no_wind():
    assert effective_temp(10.0, 1.0) == pytest.approx(10.0)

def test_effective_temp_at_threshold():
    assert effective_temp(10.0, 2.0) == pytest.approx(10.0)

def test_effective_temp_with_wind():
    # (5.0 - 2.0) / 3.0 * 0.5 = 0.5 reduction
    assert effective_temp(10.0, 5.0) == pytest.approx(9.5)


# --- fit_hdd_regression ---

def test_fit_hdd_regression_perfect_line():
    # slope=10, intercept=5: gas = 10*hdd + 5
    records = [(1.0, 15.0), (2.0, 25.0), (3.0, 35.0), (4.0, 45.0)]
    slope, intercept, r_sq = fit_hdd_regression(records)
    assert slope == pytest.approx(10.0, abs=1e-6)
    assert intercept == pytest.approx(5.0, abs=1e-6)
    assert r_sq == pytest.approx(1.0, abs=1e-6)

def test_fit_hdd_regression_r_squared_below_one():
    records = [(1.0, 15.0), (2.0, 26.0), (3.0, 34.0), (4.0, 46.0)]
    slope, intercept, r_sq = fit_hdd_regression(records)
    assert 0.0 < r_sq < 1.0

def test_fit_hdd_regression_too_few_points():
    slope, intercept, r_sq = fit_hdd_regression([(5.0, 50.0)])
    assert slope == 0.0
    assert intercept == 0.0
    assert r_sq == 0.0

def test_fit_hdd_regression_slope_non_negative():
    # Inverted data that would give a negative slope — must clamp to 0
    records = [(1.0, 50.0), (2.0, 40.0), (3.0, 30.0)]
    slope, intercept, r_sq = fit_hdd_regression(records)
    assert slope >= 0.0


# --- period_to_time ---

def test_period_to_time_midnight():
    assert period_to_time(0) == "00:00"

def test_period_to_time_half_past_midnight():
    assert period_to_time(1) == "00:30"

def test_period_to_time_seven_am():
    assert period_to_time(14) == "07:00"

def test_period_to_time_last_period():
    assert period_to_time(47) == "23:30"


# --- time_to_period ---

def test_time_to_period_midnight():
    assert time_to_period(0, 0) == 0

def test_time_to_period_seven_am():
    assert time_to_period(7, 0) == 14

def test_time_to_period_half_hour():
    assert time_to_period(0, 30) == 1

def test_time_to_period_last():
    assert time_to_period(23, 30) == 47


# --- benchmark_percentile ---

def test_benchmark_at_median():
    result = benchmark_percentile(23.0, "semi", "post_1980")
    assert result["percentile"] == pytest.approx(50.0)
    assert result["band"] == "average"

def test_benchmark_at_p25_efficient():
    result = benchmark_percentile(17.0, "semi", "post_1980")
    assert result["percentile"] == pytest.approx(25.0)
    assert result["band"] == "efficient"

def test_benchmark_at_p75_inefficient():
    result = benchmark_percentile(30.0, "semi", "post_1980")
    assert result["percentile"] == pytest.approx(75.0)
    assert result["band"] == "inefficient"

def test_benchmark_unknown_type():
    result = benchmark_percentile(20.0, "bungalow", "pre_1945")
    assert result["percentile"] is None

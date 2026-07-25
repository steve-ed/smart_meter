import pytest
from datetime import date
from s07_budget_forecast import (
    compute_monthly_budget,
    thermostat_nudge,
    project_kwh_for_day,
)


def test_monthly_budget_mean_of_twelve():
    monthly = [50.0] * 12
    assert compute_monthly_budget(monthly) == pytest.approx(50.0)

def test_monthly_budget_varying():
    monthly = [40.0, 60.0, 50.0, 80.0, 20.0, 30.0,
               10.0, 10.0, 20.0, 50.0, 70.0, 60.0]
    assert compute_monthly_budget(monthly) == pytest.approx(sum(monthly) / 12)

def test_monthly_budget_fewer_than_12_still_averages():
    monthly = [60.0, 40.0]
    assert compute_monthly_budget(monthly) == pytest.approx(50.0)


def test_project_kwh_heating_day():
    assert project_kwh_for_day(5.0, 8.0, 5.0) == pytest.approx(45.0)

def test_project_kwh_warm_day():
    assert project_kwh_for_day(0.0, 8.0, 5.0) == pytest.approx(5.0)


def test_nudge_calculates_reduction():
    result = thermostat_nudge(
        budget_gap_gbp=10.0,
        remaining_days=10,
        gas_rate_p_per_kwh=6.0,
        slope=8.0,
    )
    assert result["thermostat_reduction_c"] == pytest.approx(2.1, abs=0.1)
    assert result["budget_gap_kwh"] == pytest.approx(166.7, abs=0.5)

def test_nudge_zero_days():
    result = thermostat_nudge(10.0, 0, 6.0, 8.0)
    assert result == {}

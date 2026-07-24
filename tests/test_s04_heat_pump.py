import pytest
from s04_heat_pump import (
    cop_at_outdoor_temp,
    estimate_base_load,
    heating_kwh,
    heat_pump_payback,
    suitability_flags,
)


def test_cop_below_minus_ten_returns_one():
    assert cop_at_outdoor_temp(-15.0, flow_temp=45.0) == pytest.approx(1.0)

def test_cop_at_zero_celsius_45c_flow():
    expected = 0.45 * (45 + 273.15) / 45
    assert cop_at_outdoor_temp(0.0, flow_temp=45.0) == pytest.approx(expected, abs=0.01)

def test_cop_at_zero_celsius_55c_flow():
    expected = 0.45 * (55 + 273.15) / 55
    assert cop_at_outdoor_temp(0.0, flow_temp=55.0) == pytest.approx(expected, abs=0.01)

def test_cop_outdoor_above_flow_returns_six():
    assert cop_at_outdoor_temp(50.0, flow_temp=45.0) == pytest.approx(6.0)

def test_cop_higher_at_milder_outdoor():
    assert cop_at_outdoor_temp(10.0, 45.0) > cop_at_outdoor_temp(0.0, 45.0)


def test_estimate_base_load_summer_median():
    from datetime import date, timedelta
    daily = {}
    base = date(2024, 1, 1)
    for i in range(365):
        d = base + timedelta(days=i)
        daily[d] = 3.0 if 5 <= d.month <= 9 else 10.0
    assert estimate_base_load(daily) == pytest.approx(3.0)

def test_estimate_base_load_fallback_when_no_summer():
    from datetime import date
    daily = {date(2024, 1, i+1): 8.0 for i in range(30)}
    assert estimate_base_load(daily) == pytest.approx(3.0)


def test_heating_kwh_subtracts_base():
    assert heating_kwh(10.0, 3.0) == pytest.approx(7.0)

def test_heating_kwh_clamped_zero():
    assert heating_kwh(2.0, 5.0) == pytest.approx(0.0)


def test_payback_viable_when_short():
    result = heat_pump_payback(12000.0, annual_saving_gbp=500.0, grant_gbp=7500)
    assert result["net_cost_gbp"] == pytest.approx(4500.0)
    assert result["payback_years"] == pytest.approx(9.0, abs=0.1)
    assert result["viable"] is True

def test_payback_not_viable_when_no_saving():
    result = heat_pump_payback(12000.0, annual_saving_gbp=0.0, grant_gbp=7500)
    assert result["viable"] is False
    assert result["payback_years"] is None

def test_payback_grant_cannot_exceed_cost():
    result = heat_pump_payback(5000.0, annual_saving_gbp=300.0, grant_gbp=7500)
    assert result["net_cost_gbp"] == pytest.approx(0.0)


def _result(heating_kwh_val=8000, cop=2.8, saving=200, payback=12, viable=True, winter_summer_ratio=3.5):
    return {
        "heating_gas_kwh":         heating_kwh_val,
        "mean_seasonal_cop":       cop,
        "annual_saving_gbp":       saving,
        "payback_years":           payback,
        "viable":                  viable,
        "winter_summer_gas_ratio": winter_summer_ratio,
        "breakeven_cop":           4.0,
    }

def test_all_flags_pass():
    flags = suitability_flags(_result())
    checks = {f["check"]: f["pass"] for f in flags}
    assert checks["annual_heating_demand"] is True
    assert checks["seasonal_signal"]       is True
    assert checks["cop_above_breakeven"]   is False   # 2.8 < 4.0 breakeven
    assert checks["financial_viability"]   is True

def test_insufficient_heating_demand_fails():
    flags = suitability_flags(_result(heating_kwh_val=3000))
    checks = {f["check"]: f["pass"] for f in flags}
    assert checks["annual_heating_demand"] is False

def test_flag_count():
    flags = suitability_flags(_result())
    assert len(flags) == 4

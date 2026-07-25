import pytest
from s10_leak_frost import (
    overnight_baseline_kwh,
    detect_gas_leak,
    frost_alert,
    heating_failure_frost_alert,
)


def _make_readings(vals: list[float], month: int = 6) -> list[tuple]:
    from datetime import date
    overnight = list(range(0, 8)) + list(range(44, 48))
    return [
        (date(2025, month, 1 + i // len(overnight)), overnight[i % len(overnight)], v)
        for i, v in enumerate(vals)
    ]

def test_baseline_computes_median():
    readings = _make_readings([0.01] * 10 + [0.05] * 10 + [0.10] * 10)
    result = overnight_baseline_kwh(readings)
    assert result["median_kwh"] == pytest.approx(0.05)

def test_baseline_insufficient_data():
    readings = _make_readings([0.01] * 5)
    result = overnight_baseline_kwh(readings)
    assert result["status"] == "insufficient_data"


def _baseline(median=0.01):
    return {"median_kwh": median, "p95_kwh": 0.05, "p99_kwh": 0.08}

def test_no_leak_all_below_threshold():
    readings = [0.02] * 10
    result = detect_gas_leak(readings, _baseline(0.01))
    assert result["alert"] is False

def test_leak_six_consecutive():
    readings = [0.00, 0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.00]
    result = detect_gas_leak(readings, _baseline(0.01))
    assert result["alert"] is True
    assert result["max_consecutive_periods"] == 6

def test_leak_alert_requires_six_consecutive():
    readings = [0.10, 0.10, 0.10, 0.10, 0.10, 0.00, 0.10]
    result = detect_gas_leak(readings, _baseline(0.01))
    assert result["alert"] is False


def test_frost_no_alert_warm():
    result = frost_alert([0.0] * 12, 5.0, 4)
    assert result["alert"] is False

def test_frost_alert_vacant_high():
    result = frost_alert([0.0] * 12, 1.0, 4)
    assert result["alert"] is True
    assert result["severity"] == "HIGH"

def test_frost_alert_vacant_critical():
    result = frost_alert([0.0] * 12, -4.0, 4)
    assert result["alert"] is True
    assert result["severity"] == "CRITICAL"

def test_frost_no_alert_occupied():
    result = frost_alert([0.1] * 12, -4.0, 4)
    assert result["alert"] is False


def test_heating_failure_alert():
    result = heating_failure_frost_alert(
        expected_heating=True, actual_gas_kwh=0.05,
        outdoor_temp_c=3.0, forecast_low_c=1.0,
    )
    assert result["alert"] is True
    assert result["alert_type"] == "heating_failure_with_frost_risk"

def test_heating_failure_no_alert_boiler_running():
    result = heating_failure_frost_alert(
        expected_heating=True, actual_gas_kwh=0.5,
        outdoor_temp_c=3.0, forecast_low_c=1.0,
    )
    assert result["alert"] is False

def test_heating_failure_no_alert_warm_forecast():
    result = heating_failure_frost_alert(
        expected_heating=True, actual_gas_kwh=0.05,
        outdoor_temp_c=3.0, forecast_low_c=5.0,
    )
    assert result["alert"] is False

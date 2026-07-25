import pytest
from s05_boiler_trending import classify_trend, detect_boiler_degradation


def test_classify_trend_stable():
    weekly = [10.0, 10.1, 9.9, 10.0, 10.1, 9.8, 10.0, 10.2]
    assert classify_trend(weekly) == "stable"

def test_classify_trend_gradual():
    weekly = [10.0 + i * 0.2 for i in range(8)]
    assert classify_trend(weekly) == "gradual_trend"

def test_classify_trend_step_change():
    weekly = [10.0, 10.0, 10.0, 10.0, 12.5, 12.5, 12.5, 12.5]
    assert classify_trend(weekly) == "step_change"

def test_classify_trend_insufficient():
    assert classify_trend([10.0, 11.0]) == "insufficient_data"


def _make_records(kwh_per_hdd: float, n: int = 30) -> list[tuple[float, float]]:
    return [(5.0, 5.0 * kwh_per_hdd) for _ in range(n)]

def test_detect_no_alert():
    baseline = _make_records(10.0, 60)
    recent   = _make_records(10.5, 20)
    result   = detect_boiler_degradation(baseline, recent)
    assert result["alert"] is False
    assert result["pct_change"] == pytest.approx(5.0, abs=0.1)

def test_detect_medium_alert():
    baseline = _make_records(10.0, 60)
    recent   = _make_records(11.8, 20)
    result   = detect_boiler_degradation(baseline, recent)
    assert result["alert"] is True
    assert result["alert_severity"] == "MEDIUM"

def test_detect_high_alert():
    baseline = _make_records(10.0, 60)
    recent   = _make_records(13.0, 20)
    result   = detect_boiler_degradation(baseline, recent)
    assert result["alert"] is True
    assert result["alert_severity"] == "HIGH"

def test_detect_insufficient_baseline():
    baseline = _make_records(10.0, 10)
    recent   = _make_records(12.0, 20)
    result   = detect_boiler_degradation(baseline, recent)
    assert result["status"] == "insufficient_data"

def test_detect_insufficient_recent():
    baseline = _make_records(10.0, 60)
    recent   = _make_records(12.0, 5)
    result   = detect_boiler_degradation(baseline, recent)
    assert result["status"] == "insufficient_data"

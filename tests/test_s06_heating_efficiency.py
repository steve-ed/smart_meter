import pytest
from s06_heating_efficiency import (
    daily_efficiency_score,
    flag_anomalous_days,
)


def test_score_exactly_as_expected():
    result = daily_efficiency_score(
        actual_gas_kwh=50.0, hdd=5.0,
        slope=8.0, intercept=10.0, slope_std=3.0,
    )
    assert result["score"] == pytest.approx(100.0)
    assert result["z_score"] == pytest.approx(0.0)
    assert result["anomalous"] is False

def test_score_over_consuming():
    result = daily_efficiency_score(
        actual_gas_kwh=70.0, hdd=5.0,
        slope=8.0, intercept=10.0, slope_std=4.0,
    )
    assert result["score"] == pytest.approx(140.0)
    assert result["z_score"] == pytest.approx(5.0)
    assert result["anomalous"] is True
    assert result["anomaly_type"] == "over_consuming"

def test_score_mild_day_returns_none():
    result = daily_efficiency_score(
        actual_gas_kwh=5.0, hdd=0.3,
        slope=8.0, intercept=10.0, slope_std=3.0,
    )
    assert result["score"] is None
    assert result["reason"] == "too_mild"


def _make_scores(anomalous_flags: list[bool]) -> list[dict]:
    return [
        {"anomalous": a, "score": 120.0 if a else 100.0,
         "anomaly_type": "over_consuming" if a else None}
        for a in anomalous_flags
    ]

def test_flag_three_consecutive():
    scores = _make_scores([False, True, True, True, False])
    winds  = [3.0, 3.0, 3.0, 3.0, 3.0]
    result = flag_anomalous_days(scores, winds)
    assert result[1]["sustained_alert"] is True
    assert result[2]["sustained_alert"] is True
    assert result[3]["sustained_alert"] is True
    assert result[0]["sustained_alert"] is False

def test_flag_suppressed_by_wind():
    scores = _make_scores([True, True, True])
    winds  = [9.0, 9.0, 9.0]
    result = flag_anomalous_days(scores, winds)
    assert all(not r["sustained_alert"] for r in result)

def test_flag_two_consecutive_not_enough():
    scores = _make_scores([True, True, False, False])
    winds  = [3.0, 3.0, 3.0, 3.0]
    result = flag_anomalous_days(scores, winds)
    assert all(not r["sustained_alert"] for r in result)

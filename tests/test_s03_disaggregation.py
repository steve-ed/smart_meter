import pytest
from s03_disaggregation import (
    compute_residual,
    detect_events,
    match_event,
    aggregate_appliance_evidence,
)


def test_residual_subtracts_expected():
    readings = [{"weekday": 0, "period_index": 0, "elec_kwh": 1.5, "timestamp": "2024-01-01 00:00"}]
    profile  = {(0, 0): 1.0}
    result   = compute_residual(readings, profile)
    assert result[0]["residual_kwh"] == pytest.approx(0.5)

def test_residual_clamped_to_zero():
    readings = [{"weekday": 0, "period_index": 0, "elec_kwh": 0.2, "timestamp": "2024-01-01 00:00"}]
    profile  = {(0, 0): 1.0}
    result   = compute_residual(readings, profile)
    assert result[0]["residual_kwh"] == pytest.approx(0.0)

def test_residual_missing_slot_uses_zero_background():
    readings = [{"weekday": 3, "period_index": 5, "elec_kwh": 0.8, "timestamp": "2024-01-04 02:30"}]
    profile  = {}
    result   = compute_residual(readings, profile)
    assert result[0]["residual_kwh"] == pytest.approx(0.8)


def _residual_seq(values, start_period=0):
    return [
        {"timestamp": f"2024-01-01 {(start_period+i)//2:02d}:{((start_period+i)%2)*30:02d}",
         "date": "2024-01-01",
         "period_index": start_period + i,
         "residual_kwh": v}
        for i, v in enumerate(values)
    ]

def test_detect_single_event():
    seq = _residual_seq([0.0, 0.5, 0.6, 0.0])
    events = detect_events(seq)
    assert len(events) == 1
    assert events[0]["duration_periods"] == 2
    assert events[0]["total_kwh"] == pytest.approx(1.1)

def test_detect_two_separate_events():
    seq = _residual_seq([0.5, 0.0, 0.5])
    events = detect_events(seq)
    assert len(events) == 2

def test_detect_no_event_below_threshold():
    seq = _residual_seq([0.10, 0.20, 0.24])
    events = detect_events(seq)
    assert len(events) == 0

def test_detect_event_fields():
    seq = _residual_seq([0.3, 0.8, 0.5])
    events = detect_events(seq)
    assert len(events) == 1
    e = events[0]
    assert e["peak_kwh_per_period"] == pytest.approx(0.8)
    assert e["mean_kwh_per_period"] == pytest.approx((0.3 + 0.8 + 0.5) / 3, abs=0.001)
    assert e["start_period"] == 0
    assert e["end_period"]   == 2


def _event(duration=6, peak=3.0, start=2):
    return {
        "duration_periods":    duration,
        "peak_kwh_per_period": peak,
        "mean_kwh_per_period": peak * 0.9,
        "total_kwh":           peak * duration,
        "start_period":        start,
    }

def test_match_ev_fast():
    e = _event(duration=8, peak=3.2, start=2)
    matches = match_event(e)
    names = [m[0] for m in matches]
    assert "ev_fast" in names

def test_match_immersion():
    e = _event(duration=2, peak=1.5, start=5)
    matches = match_event(e)
    names = [m[0] for m in matches]
    assert "immersion" in names

def test_match_returns_confidence_between_0_and_1():
    e = _event(duration=3, peak=1.0, start=20)
    matches = match_event(e)
    for _, conf in matches:
        assert 0.0 <= conf <= 1.0

def test_match_low_confidence_excluded():
    e = _event(duration=1, peak=10.0, start=0)
    matches = match_event(e)
    assert all(conf >= 0.40 for _, conf in matches)


def _events_for(n=5, duration=8, peak=3.2, start=2):
    return [_event(duration=duration, peak=peak, start=start)] * n

def test_aggregate_likely_present_when_enough_matches():
    events = _events_for(n=6)
    result = aggregate_appliance_evidence(events)
    assert "ev_fast" in result
    assert result["ev_fast"]["likely_present"] is True

def test_aggregate_not_present_too_few_matches():
    events = _events_for(n=3)
    result = aggregate_appliance_evidence(events)
    if "ev_fast" in result:
        assert result["ev_fast"]["likely_present"] is False

def test_aggregate_returns_match_count():
    events = _events_for(n=6)
    result = aggregate_appliance_evidence(events)
    assert result["ev_fast"]["match_count"] >= 6

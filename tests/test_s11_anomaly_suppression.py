# tests/test_s11_anomaly_suppression.py
import pytest
from s11_anomaly_suppression import (
    detect_flatlines,
    build_spike_baseline,
    classify_spike,
    apply_occupancy_suppression,
)


# --- detect_flatlines ---

def test_flatlines_single_qualifying_run():
    readings = [0.0] * 6 + [1.0]
    result = detect_flatlines(readings, threshold=0.010, min_periods=6)
    assert result == [(0, 5)]


def test_flatlines_two_separate_runs():
    readings = [0.0] * 6 + [1.0] + [0.0] * 7
    result = detect_flatlines(readings)
    assert result == [(0, 5), (7, 13)]


def test_flatlines_run_below_min_not_returned():
    readings = [0.0] * 5 + [1.0]
    result = detect_flatlines(readings, min_periods=6)
    assert result == []


def test_flatlines_run_exactly_at_min_returned():
    readings = [0.0] * 6
    result = detect_flatlines(readings, min_periods=6)
    assert result == [(0, 5)]


def test_flatlines_all_above_threshold_empty():
    readings = [0.5] * 48
    result = detect_flatlines(readings)
    assert result == []


# --- build_spike_baseline ---

def _make_day(weekday, period_values):
    """Build a day-dict with 48 periods from a dict of {period_index: elec_kwh}."""
    periods = []
    for i in range(48):
        periods.append({
            "period_index": i,
            "elec_kwh": period_values.get(i, 0.0),
            "occupied_label": "UNKNOWN",
            "floor_kwh": 0.0,
        })
    return {"date": "2025-01-01", "weekday": weekday, "periods": periods}


def test_build_spike_baseline_correct_median_and_mad():
    # Monday, period 0: readings [1.0, 3.0, 2.0]
    days = [
        _make_day(0, {0: 1.0}),
        _make_day(0, {0: 3.0}),
        _make_day(0, {0: 2.0}),
    ]
    # Update dates to be different (weekday is what matters for the key)
    days[1]["date"] = "2025-01-08"
    days[2]["date"] = "2025-01-15"
    baseline = build_spike_baseline(days)
    median, mad = baseline[(0, 0)]
    assert median == pytest.approx(2.0)
    assert mad == pytest.approx(1.0)


def test_build_spike_baseline_mad_floored_at_0_05():
    # All identical readings → raw MAD = 0 → floored to 0.05
    days = [_make_day(0, {0: 1.0}) for _ in range(3)]
    baseline = build_spike_baseline(days)
    _, mad = baseline[(0, 0)]
    assert mad == pytest.approx(0.05)


def test_build_spike_baseline_separate_weekday_entries():
    mon_day = _make_day(0, {0: 1.0})
    tue_day = _make_day(1, {0: 2.0})
    tue_day["date"] = "2025-01-07"
    baseline = build_spike_baseline([mon_day, tue_day])
    assert (0, 0) in baseline
    assert (1, 0) in baseline
    assert baseline[(0, 0)][0] == pytest.approx(1.0)
    assert baseline[(1, 0)][0] == pytest.approx(2.0)


# --- classify_spike ---

def test_classify_spike_below_threshold_returns_none():
    # threshold = 1.0 + 4.0 * 0.05 = 1.2
    assert classify_spike(1.1, median=1.0, mad=0.05, occupancy="OCCUPIED") is None


def test_classify_spike_above_threshold_occupied():
    assert classify_spike(2.0, median=1.0, mad=0.05, occupancy="OCCUPIED") == "SPIKE_OCCUPIED"


def test_classify_spike_above_threshold_vacant():
    assert classify_spike(2.0, median=1.0, mad=0.05, occupancy="VACANT") == "SPIKE_VACANT"


def test_classify_spike_above_threshold_unknown():
    assert classify_spike(2.0, median=1.0, mad=0.05, occupancy="UNKNOWN") == "SPIKE_UNKNOWN"


def test_classify_spike_mad_floor_applied():
    # mad=0.01 → floored to 0.05 → threshold = 1.0 + 4*0.05 = 1.2
    # reading=1.1 is below threshold
    assert classify_spike(1.1, median=1.0, mad=0.01, occupancy="OCCUPIED") is None
    # reading=1.3 is above threshold
    assert classify_spike(1.3, median=1.0, mad=0.01, occupancy="OCCUPIED") == "SPIKE_OCCUPIED"


# --- apply_occupancy_suppression ---

def test_suppression_flatline_occupied():
    r = apply_occupancy_suppression("FLATLINE", "OCCUPIED")
    assert r == {"priority": "HIGH", "suppressed": False, "suppress_reason": None}


def test_suppression_flatline_vacant():
    r = apply_occupancy_suppression("FLATLINE", "VACANT")
    assert r == {"priority": "HIGH", "suppressed": True, "suppress_reason": "vacancy"}


def test_suppression_flatline_unknown():
    r = apply_occupancy_suppression("FLATLINE", "UNKNOWN")
    assert r == {"priority": "LOW", "suppressed": False, "suppress_reason": None}


def test_suppression_spike_vacant():
    r = apply_occupancy_suppression("SPIKE_VACANT", "VACANT")
    assert r == {"priority": "HIGH", "suppressed": False, "suppress_reason": None}


def test_suppression_spike_occupied():
    r = apply_occupancy_suppression("SPIKE_OCCUPIED", "OCCUPIED")
    assert r == {"priority": "MEDIUM", "suppressed": False, "suppress_reason": None}


def test_suppression_spike_unknown():
    r = apply_occupancy_suppression("SPIKE_UNKNOWN", "UNKNOWN")
    assert r == {"priority": "LOW", "suppressed": False, "suppress_reason": None}

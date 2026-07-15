import pandas as pd
import pytest
from anomaly_detector import (
    detect_anomalies,
    _detect_spikes,
    _detect_prolonged,
    _detect_flatlines,
    BASELINE_DAYS,
    _HALFHOURS_PER_DAY,
)


def make_group(values, mpxn="TEST", utility="electricity", start="2021-01-01"):
    """Build a minimal DataFrame matching the format detect_anomalies expects."""
    timestamps = pd.date_range(start=start, periods=len(values), freq="30min")
    return pd.DataFrame({
        "mpxn": mpxn,
        "utility": utility,
        "timestamp": timestamps,
        "value": [float(v) for v in values],
    })


def test_spike_detects_value_above_threshold():
    # 28 days of baseline at 1.0, then one reading at 10.0 (10× baseline — exceeds 3×)
    baseline = [1.0] * (BASELINE_DAYS * _HALFHOURS_PER_DAY)
    group = make_group(baseline + [10.0])
    events = _detect_spikes(group, "TEST", "electricity")
    assert len(events) == 1
    assert events[0]["anomaly_type"] == "spike"
    assert events[0]["value"] == 10.0
    assert events[0]["ratio"] == pytest.approx(10.0, rel=0.01)


def test_spike_does_not_flag_normal_reading():
    readings = [1.0] * (BASELINE_DAYS * _HALFHOURS_PER_DAY + 1)
    group = make_group(readings)
    events = _detect_spikes(group, "TEST", "electricity")
    assert len(events) == 0


def test_spike_skips_when_insufficient_baseline():
    # Only 5 readings — below the min_periods threshold
    group = make_group([1.0, 1.0, 1.0, 1.0, 100.0])
    events = _detect_spikes(group, "TEST", "electricity")
    assert len(events) == 0


def test_spike_excludes_zeros_from_gas_baseline():
    # Gas: baseline of alternating 0 and 2.0; spike at 20.0
    # Mean of non-zero values = 2.0; 20.0 / 2.0 = 10× > 3× threshold
    baseline = ([0.0, 2.0] * (BASELINE_DAYS * _HALFHOURS_PER_DAY // 2))
    group = make_group(baseline + [20.0], utility="gas")
    events = _detect_spikes(group, "TEST", "gas")
    assert len(events) == 1


def test_prolonged_detects_three_consecutive_elevated_days():
    # 28 days baseline at 1.0/HH (48/day), then 4 days at 3.0/HH (144/day = 3× baseline daily)
    baseline = [1.0] * (BASELINE_DAYS * _HALFHOURS_PER_DAY)
    elevated = [3.0] * (4 * _HALFHOURS_PER_DAY)
    group = make_group(baseline + elevated)
    events = _detect_prolonged(group, "TEST", "electricity")
    assert len(events) == 1
    assert events[0]["anomaly_type"] == "prolonged"
    assert events[0]["ratio"] == pytest.approx(2.8, rel=0.05)


def test_prolonged_does_not_flag_two_consecutive_elevated_days():
    baseline = [1.0] * (BASELINE_DAYS * _HALFHOURS_PER_DAY)
    elevated = [3.0] * (2 * _HALFHOURS_PER_DAY)
    group = make_group(baseline + elevated)
    events = _detect_prolonged(group, "TEST", "electricity")
    assert len(events) == 0


def test_prolonged_does_not_flag_with_insufficient_baseline():
    # Only 10 days of data — below min_periods for the rolling window
    group = make_group([1.0] * (10 * _HALFHOURS_PER_DAY))
    events = _detect_prolonged(group, "TEST", "electricity")
    assert len(events) == 0


def test_prolonged_detects_two_separate_runs():
    baseline = [1.0] * (BASELINE_DAYS * _HALFHOURS_PER_DAY)
    elevated = [10.0] * (4 * _HALFHOURS_PER_DAY)
    gap      = [1.0] * _HALFHOURS_PER_DAY
    group = make_group(baseline + elevated + gap + elevated)
    events = _detect_prolonged(group, "TEST", "electricity")
    assert len(events) == 2


def test_flatline_detects_24_consecutive_zero_hours():
    # 24 hours = 48 half-hours of zeros, surrounded by non-zero readings
    normal = [1.0] * _HALFHOURS_PER_DAY
    zeros  = [0.0] * _HALFHOURS_PER_DAY   # exactly 24 hours
    group = make_group(normal + zeros + [1.0] * 10)
    events = _detect_flatlines(group, "TEST", "electricity")
    assert len(events) == 1
    assert events[0]["anomaly_type"] == "flat_line"
    assert events[0]["value"] == 0.0
    assert events[0]["baseline"] is None


def test_flatline_does_not_flag_short_zero_run():
    normal = [1.0] * _HALFHOURS_PER_DAY
    zeros  = [0.0] * 10   # only 5 hours
    group = make_group(normal + zeros + [1.0] * 10)
    events = _detect_flatlines(group, "TEST", "electricity")
    assert len(events) == 0


def test_flatline_detects_run_at_end_of_series():
    normal = [1.0] * _HALFHOURS_PER_DAY
    zeros  = [0.0] * _HALFHOURS_PER_DAY
    group = make_group(normal + zeros)
    events = _detect_flatlines(group, "TEST", "electricity")
    assert len(events) == 1


def test_flatline_detects_multiple_separate_runs():
    normal = [1.0] * _HALFHOURS_PER_DAY
    zeros  = [0.0] * _HALFHOURS_PER_DAY
    group = make_group(zeros + normal + zeros)
    events = _detect_flatlines(group, "TEST", "electricity")
    assert len(events) == 2


def test_flatline_does_not_flag_47_zeros():
    # 47 half-hours = 23.5 hours, one below the 24-hour threshold
    normal = [1.0] * _HALFHOURS_PER_DAY
    zeros  = [0.0] * 47
    group = make_group(normal + zeros + [1.0])
    events = _detect_flatlines(group, "TEST", "electricity")
    assert len(events) == 0

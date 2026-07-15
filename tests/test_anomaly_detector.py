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

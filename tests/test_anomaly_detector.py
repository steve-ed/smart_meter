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

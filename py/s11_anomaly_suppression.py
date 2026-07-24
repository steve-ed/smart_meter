"""s11_anomaly_suppression.py — Pure functions for anomaly detection with occupancy suppression."""

import csv
import statistics
from datetime import datetime

from config import METERS
from tier3_lib import load_labeled_days

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

FLATLINE_THRESHOLD_KWH = 0.010
FLATLINE_MIN_PERIODS   = 6
SPIKE_K                = 4.0
MAD_FLOOR              = 0.05
ANALYSIS_WEEKS         = 8
TOTAL_WEEKS            = 16

CSV_PATH = "data/s11_anomaly_suppression.csv"
CSV_COLUMNS = [
    "meter_id", "alert_type", "priority", "suppressed", "suppress_reason",
    "occupancy_state", "start_date", "start_period", "end_date", "end_period",
    "duration_periods", "mean_kwh", "baseline_median_kwh", "baseline_mad_kwh",
]


# ---------------------------------------------------------------------------
# Pure functions
# ---------------------------------------------------------------------------

def detect_flatlines(readings, threshold=0.010, min_periods=6):
    """Return [(start_idx, end_idx)] for contiguous runs below threshold lasting >= min_periods.

    Args:
        readings: list of floats of any length
        threshold: readings strictly below this value count as flat
        min_periods: minimum consecutive flat periods to qualify

    Returns:
        List of (start_idx, end_idx) tuples, indices inclusive.
    """
    result = []
    n = len(readings)
    i = 0
    while i < n:
        if readings[i] < threshold:
            start = i
            while i < n and readings[i] < threshold:
                i += 1
            end = i - 1
            if (end - start + 1) >= min_periods:
                result.append((start, end))
        else:
            i += 1
    return result


def build_spike_baseline(days):
    """Compute (median_kwh, mad_kwh) per (weekday, period_index) slot.

    Args:
        days: list of dicts with keys "weekday" (int 0-6) and "periods"
              (list of dicts with "period_index" and "elec_kwh")

    Returns:
        dict mapping (weekday, period_index) -> (median, mad)
        MAD is floored at MAD_FLOOR (0.05).
    """
    slot_readings = {}
    for day in days:
        weekday = day["weekday"]
        for period in day["periods"]:
            key = (weekday, period["period_index"])
            slot_readings.setdefault(key, []).append(period["elec_kwh"])

    baseline = {}
    for key, values in slot_readings.items():
        med = statistics.median(values)
        raw_mad = statistics.median([abs(v - med) for v in values])
        mad = max(raw_mad, MAD_FLOOR)
        baseline[key] = (med, mad)
    return baseline


def classify_spike(reading, median, mad, occupancy, k=4.0):
    """Classify a reading as a spike, accounting for occupancy.

    Args:
        reading: observed elec_kwh value
        median: baseline median for this (weekday, period_index) slot
        mad: baseline MAD for this slot
        occupancy: "OCCUPIED", "VACANT", or "UNKNOWN"
        k: multiplier for spike threshold

    Returns:
        None if reading is within threshold; otherwise "SPIKE_VACANT",
        "SPIKE_OCCUPIED", or "SPIKE_UNKNOWN".
    """
    threshold = median + k * max(mad, MAD_FLOOR)
    if reading <= threshold:
        return None
    if occupancy == "VACANT":
        return "SPIKE_VACANT"
    if occupancy == "OCCUPIED":
        return "SPIKE_OCCUPIED"
    return "SPIKE_UNKNOWN"


_SUPPRESSION_TABLE = {
    ("FLATLINE",      "OCCUPIED"): ("HIGH",   False, None),
    ("FLATLINE",      "VACANT"):   ("HIGH",   True,  "vacancy"),
    ("FLATLINE",      "UNKNOWN"):  ("LOW",    False, None),
    ("SPIKE_VACANT",  "VACANT"):   ("HIGH",   False, None),
    ("SPIKE_OCCUPIED","OCCUPIED"): ("MEDIUM", False, None),
    ("SPIKE_UNKNOWN", "UNKNOWN"):  ("LOW",    False, None),
}


def apply_occupancy_suppression(alert_type, occupancy):
    """Return suppression metadata for an alert given occupancy state.

    Args:
        alert_type: "FLATLINE", "SPIKE_VACANT", "SPIKE_OCCUPIED", or "SPIKE_UNKNOWN"
        occupancy: "OCCUPIED", "VACANT", or "UNKNOWN"

    Returns:
        dict with keys "priority" (str), "suppressed" (bool), "suppress_reason" (str | None)
    """
    priority, suppressed, suppress_reason = _SUPPRESSION_TABLE[(alert_type, occupancy)]
    return {"priority": priority, "suppressed": suppressed, "suppress_reason": suppress_reason}

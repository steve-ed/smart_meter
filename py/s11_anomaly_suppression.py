"""
Service #11 — Vacancy-Aware Anomaly Suppression.
Detects electricity flat-line and spike anomalies; suppresses false positives
using occupancy labels from ElecOccupancyDetector.
"""

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

def detect_flatlines(
    readings: list[float],
    threshold: float = FLATLINE_THRESHOLD_KWH,
    min_periods: int = FLATLINE_MIN_PERIODS,
) -> list[tuple[int, int]]:
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


def build_spike_baseline(
    days: list[dict],
) -> dict[tuple[int, int], tuple[float, float]]:
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


def classify_spike(
    reading: float,
    median: float,
    mad: float,
    occupancy: str,
    k: float = SPIKE_K,
) -> str | None:
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


def apply_occupancy_suppression(alert_type: str, occupancy: str) -> dict:
    """Return suppression metadata for an alert given occupancy state.

    Args:
        alert_type: "FLATLINE", "SPIKE_VACANT", "SPIKE_OCCUPIED", or "SPIKE_UNKNOWN"
        occupancy: "OCCUPIED", "VACANT", or "UNKNOWN"

    Returns:
        dict with keys "priority" (str), "suppressed" (bool), "suppress_reason" (str | None)
    """
    key = (alert_type, occupancy)
    if key not in _SUPPRESSION_TABLE:
        raise KeyError(f"No suppression rule for ({alert_type!r}, {occupancy!r})")
    priority, suppressed, suppress_reason = _SUPPRESSION_TABLE[key]
    return {"priority": priority, "suppressed": suppressed, "suppress_reason": suppress_reason}


# ---------------------------------------------------------------------------
# Per-meter analysis
# ---------------------------------------------------------------------------

def analyse_meter(meter_id: int, all_days: list[dict]) -> list[dict]:
    """Analyse one meter's days and return a list of alert row dicts."""
    if len(all_days) < ANALYSIS_WEEKS * 7:
        return []

    analysis_days = all_days[-(ANALYSIS_WEEKS * 7):]
    baseline = build_spike_baseline(all_days)

    flat: list[tuple[str, int, float, int, str]] = []
    for day in analysis_days:
        for p in day["periods"]:
            flat.append((day["date"], p["period_index"], p["elec_kwh"], day["weekday"], p["occupied_label"]))

    elec_series = [entry[2] for entry in flat]
    alerts: list[dict] = []

    # Flat-line alerts
    for start_idx, end_idx in detect_flatlines(elec_series):
        run = flat[start_idx : end_idx + 1]

        # Plurality vote on occupancy
        occupancy_counts: dict[str, int] = {}
        for entry in run:
            occupancy_counts[entry[4]] = occupancy_counts.get(entry[4], 0) + 1
        for label in ("OCCUPIED", "VACANT", "UNKNOWN"):
            if occupancy_counts.get(label, 0) >= max(occupancy_counts.values()):
                occupancy = label
                break
        else:
            occupancy = "UNKNOWN"

        start_date, start_period = run[0][0], run[0][1]
        end_date, end_period = run[-1][0], run[-1][1]
        mean_kwh = sum(e[2] for e in run) / len(run)
        wd = run[0][3]
        base_med, base_mad = baseline.get((wd, start_period), (0.0, MAD_FLOOR))
        suppression = apply_occupancy_suppression("FLATLINE", occupancy)

        alerts.append({
            "alert_type": "FLATLINE",
            "priority": suppression["priority"],
            "suppressed": suppression["suppressed"],
            "suppress_reason": suppression["suppress_reason"] if suppression["suppress_reason"] is not None else "",
            "occupancy_state": occupancy,
            "start_date": start_date,
            "start_period": start_period,
            "end_date": end_date,
            "end_period": end_period,
            "duration_periods": len(run),
            "mean_kwh": round(mean_kwh, 4),
            "baseline_median_kwh": round(base_med, 4),
            "baseline_mad_kwh": round(base_mad, 4),
        })

    # Spike alerts
    for entry in flat:
        date, period_index, elec_kwh, weekday, occupied_label = entry
        key = (weekday, period_index)
        if key not in baseline:
            continue
        base_med, base_mad = baseline[key]
        spike_type = classify_spike(elec_kwh, base_med, base_mad, occupied_label)
        if spike_type is None:
            continue
        suppression = apply_occupancy_suppression(spike_type, occupied_label)
        alerts.append({
            "alert_type": spike_type,
            "priority": suppression["priority"],
            "suppressed": suppression["suppressed"],
            "suppress_reason": suppression["suppress_reason"] if suppression["suppress_reason"] is not None else "",
            "occupancy_state": occupied_label,
            "start_date": date,
            "start_period": period_index,
            "end_date": date,
            "end_period": period_index,
            "duration_periods": 1,
            "mean_kwh": round(elec_kwh, 4),
            "baseline_median_kwh": round(base_med, 4),
            "baseline_mad_kwh": round(base_mad, 4),
        })

    return alerts


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    all_rows: list[dict] = []

    for meter_id in sorted(METERS):
        all_days = load_labeled_days(meter_id, weeks=TOTAL_WEEKS)
        if len(all_days) < TOTAL_WEEKS * 7:
            print(f"M{meter_id}: insufficient history ({len(all_days)} days), skipping")
            continue

        alerts = analyse_meter(meter_id, all_days)

        n_suppressed = sum(1 for a in alerts if a["suppressed"])
        n_flatline   = sum(1 for a in alerts if a["alert_type"] == "FLATLINE")
        n_spike      = sum(1 for a in alerts if a["alert_type"].startswith("SPIKE"))
        print(
            f"M{meter_id}: {len(alerts)} alerts ({n_suppressed} suppressed)"
            f" — {n_flatline} flatline, {n_spike} spike"
        )

        for alert in alerts:
            row = {"meter_id": meter_id}
            row.update(alert)
            all_rows.append(row)

    with open(CSV_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\nWrote {len(all_rows)} rows to {CSV_PATH}")


if __name__ == "__main__":
    main()

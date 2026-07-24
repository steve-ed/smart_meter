"""
Service #3 — Appliance Load Disaggregation.

Run: python py/s03_disaggregation.py
Outputs: data/s03_disaggregation.csv
"""

import csv

from config import METERS
from tier1_lib import load_electricity, build_weekly_profile

OUT_FILE            = "data/s03_disaggregation.csv"
DETECTION_THRESHOLD = 0.25
MIN_MATCH_COUNT     = 4
MIN_CONFIDENCE      = 0.55

SIGNATURES = {
    "ev_fast":    {"duration": (4, 48),  "peak_kwh": (2.5, 4.0),  "affinity": range(0, 14)},
    "ev_slow":    {"duration": (8, 48),  "peak_kwh": (1.5, 2.0),  "affinity": range(0, 14)},
    "immersion":  {"duration": (1,  6),  "peak_kwh": (1.3, 1.8),
                   "affinity": list(range(0, 8)) + list(range(32, 40))},
    "shower":     {"duration": (1,  2),  "peak_kwh": (0.7, 2.8),
                   "affinity": list(range(12, 20)) + list(range(34, 42))},
    "washing":    {"duration": (1,  4),  "peak_kwh": (0.4, 1.3),  "affinity": range(14, 40)},
    "dishwasher": {"duration": (2,  5),  "peak_kwh": (0.4, 1.3),  "affinity": range(36, 48)},
    "oven":       {"duration": (1,  4),  "peak_kwh": (0.9, 1.8),  "affinity": range(30, 44)},
}


def compute_residual(readings: list[dict], profile: dict) -> list[dict]:
    result = []
    for r in readings:
        expected = profile.get((r["weekday"], r["period_index"]), 0.0)
        residual = max(r["elec_kwh"] - expected, 0.0)
        result.append({
            "timestamp":    r["timestamp"],
            "date":         r["timestamp"][:10],
            "period_index": r["period_index"],
            "residual_kwh": round(residual, 4),
        })
    return result


def detect_events(residual: list[dict]) -> list[dict]:
    events = []
    current = None
    for r in residual:
        if r["residual_kwh"] >= DETECTION_THRESHOLD:
            if current is None:
                current = {"date": r["date"], "start_period": r["period_index"],
                           "end_period": r["period_index"], "periods": [r["residual_kwh"]]}
            else:
                current["end_period"] = r["period_index"]
                current["periods"].append(r["residual_kwh"])
        else:
            if current is not None:
                events.append(_finalise_event(current))
                current = None
    if current:
        events.append(_finalise_event(current))
    return events


def _finalise_event(ev: dict) -> dict:
    periods = ev["periods"]
    duration = len(periods)
    total_kwh = sum(periods)
    return {
        "date":                ev["date"],
        "start_period":        ev["start_period"],
        "end_period":          ev["end_period"],
        "duration_periods":    duration,
        "total_kwh":           round(total_kwh, 3),
        "peak_kwh_per_period": round(max(periods), 3),
        "mean_kwh_per_period": round(total_kwh / duration, 3),
    }


def match_event(event: dict) -> list[tuple[str, float]]:
    matches = []
    dur   = event["duration_periods"]
    peak  = event["peak_kwh_per_period"]
    start = event["start_period"]

    for appliance, sig in SIGNATURES.items():
        score = 0.0
        denom = 0.0

        d_lo, d_hi = sig["duration"]
        if d_lo <= dur <= d_hi:
            score += 1.0
        elif dur < d_lo:
            score += max(0.0, 1.0 - (d_lo - dur) * 0.3)
        denom += 1.0

        p_lo, p_hi = sig["peak_kwh"]
        if p_lo <= peak <= p_hi:
            score += 1.0
        elif peak > p_hi:
            score += max(0.0, 1.0 - (peak - p_hi) / p_hi * 0.5)
        elif peak < p_lo:
            score += max(0.0, 1.0 - (p_lo - peak) / p_lo * 0.8)
        denom += 1.0

        if start in sig["affinity"]:
            score += 0.5
        denom += 0.5

        confidence = score / denom
        if confidence >= 0.40:
            matches.append((appliance, round(confidence, 2)))

    matches.sort(key=lambda x: -x[1])
    return matches


def aggregate_appliance_evidence(events: list[dict]) -> dict[str, dict]:
    appliance_confs: dict[str, list[float]] = {}
    for event in events:
        for appliance, confidence in match_event(event):
            appliance_confs.setdefault(appliance, []).append(confidence)

    results = {}
    for appliance, confs in appliance_confs.items():
        count     = len(confs)
        mean_conf = sum(confs) / count
        results[appliance] = {
            "match_count":     count,
            "mean_confidence": round(mean_conf, 2),
            "likely_present":  count >= MIN_MATCH_COUNT and mean_conf >= MIN_CONFIDENCE,
        }
    return results


def analyse_meter(meter_id: int) -> list[dict]:
    readings = load_electricity(meter_id)
    if not readings:
        print(f"  M{meter_id}: no electricity data")
        return []

    profile  = build_weekly_profile(readings)
    residual = compute_residual(readings, profile)
    events   = detect_events(residual)
    evidence = aggregate_appliance_evidence(events)

    present = [a for a, e in evidence.items() if e["likely_present"]]
    print(f"  M{meter_id}: {len(events)} events  likely present: {present or 'none'}")

    rows = []
    for appliance in sorted(SIGNATURES):
        ev = evidence.get(appliance, {"match_count": 0, "mean_confidence": 0.0, "likely_present": False})
        rows.append({
            "meter_id":        meter_id,
            "appliance":       appliance,
            "match_count":     ev["match_count"],
            "mean_confidence": ev["mean_confidence"],
            "likely_present":  ev["likely_present"],
        })
    return rows


def main():
    print("Service #3 — Appliance Load Disaggregation\n")
    all_rows = []
    for meter_id in sorted(METERS):
        all_rows.extend(analyse_meter(meter_id))

    fields = ["meter_id", "appliance", "match_count", "mean_confidence", "likely_present"]
    with open(OUT_FILE, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(all_rows)
    print(f"\nWrote {len(all_rows)} rows to {OUT_FILE}")


if __name__ == "__main__":
    main()

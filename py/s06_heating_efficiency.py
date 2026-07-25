"""
Service #6 — Heating Efficiency Scoring.

For each meter, fits an HDD regression (heating season days HDD > 0.5,
R² >= 0.60 required) and scores every heating day in WINTER_START–WINTER_END.
Flags sustained anomalous days (z > 2.5 for 3+ consecutive days, wind < 8 m/s).
Benchmarks each meter against UK peer properties.

Run: python py/s06_heating_efficiency.py
Outputs: data/s06_heating_efficiency.csv
"""

import csv
import math
from datetime import date

from config import (
    GAS_RATE_P_KWH,
    METERS,
    METER_META,
    REGRESSION_START,
    REGRESSION_END,
    WINTER_START,
    WINTER_END,
)
from tier2_lib import (
    build_daily_gas_hdd,
    fit_hdd_regression,
    benchmark_percentile,
    load_weather,
)

OUT_FILE = "data/s06_heating_efficiency.csv"
MIN_R2   = 0.60
Z_ALERT  = 2.5
WIND_SUPPRESS_MS = 8.0
CONSECUTIVE_MIN  = 3


def daily_efficiency_score(actual_gas_kwh: float,
                            hdd: float,
                            slope: float,
                            intercept: float,
                            slope_std: float) -> dict:
    if hdd < 0.5:
        return {"score": None, "reason": "too_mild"}
    expected_kwh = slope * hdd + intercept
    residual_kwh = actual_gas_kwh - expected_kwh
    z_score      = residual_kwh / max(slope_std, 1.0)
    score        = round(100 * actual_gas_kwh / expected_kwh, 1) if expected_kwh > 0 else None
    anomalous    = abs(z_score) > Z_ALERT
    anomaly_type = None
    if anomalous:
        anomaly_type = "over_consuming" if z_score > 0 else "under_consuming"
    return {
        "score":        score,
        "expected_kwh": round(expected_kwh, 2),
        "actual_kwh":   round(actual_gas_kwh, 2),
        "residual_kwh": round(residual_kwh, 2),
        "z_score":      round(z_score, 2),
        "anomalous":    anomalous,
        "anomaly_type": anomaly_type,
    }


def flag_anomalous_days(daily_scores: list[dict],
                         daily_wind_ms: list[float]) -> list[dict]:
    """
    Mark sustained_alert=True on days where z > Z_ALERT for 3+ consecutive days
    and wind < WIND_SUPPRESS_MS.
    """
    n = len(daily_scores)
    result = [dict(s, sustained_alert=False) for s in daily_scores]

    for i in range(n - CONSECUTIVE_MIN + 1):
        window = [(daily_scores[i + j], daily_wind_ms[i + j])
                  for j in range(CONSECUTIVE_MIN)]
        if all(s.get("anomalous") and w < WIND_SUPPRESS_MS
               for s, w in window):
            for j in range(CONSECUTIVE_MIN):
                result[i + j]["sustained_alert"] = True

    return result


def _residual_std(records: list[tuple[float, float]],
                   slope: float,
                   intercept: float) -> float:
    residuals = [g - (slope * h + intercept) for h, g in records]
    n = len(residuals)
    if n < 2:
        return 1.0
    mean_r = sum(residuals) / n
    return math.sqrt(sum((r - mean_r) ** 2 for r in residuals) / (n - 1))


def analyse_meter(meter_id: int) -> list[dict]:
    meta = METER_META[meter_id]

    regression_days = build_daily_gas_hdd(meter_id, REGRESSION_START, REGRESSION_END)
    heating_days    = [(d["hdd"], d["gas_kwh"]) for d in regression_days if d["hdd"] > 0.5]

    if len(heating_days) < 60:
        print(f"  M{meter_id}: insufficient heating days ({len(heating_days)}) — skipping")
        return []

    slope, intercept, r_sq = fit_hdd_regression(heating_days)
    if r_sq < MIN_R2:
        print(f"  M{meter_id}: R²={r_sq:.2f} < {MIN_R2} — regression too weak, skipping")
        return []

    slope_std = _residual_std(heating_days, slope, intercept)

    winter_days = build_daily_gas_hdd(meter_id, WINTER_START, WINTER_END)
    weather_map = {r["timestamp"][:10]: float(r["wind_speed_ms"])
                   for r in load_weather()}

    scored = []
    for d in winter_days:
        s = daily_efficiency_score(d["gas_kwh"], d["hdd"], slope, intercept, slope_std)
        s["date"]    = d["date"]
        s["hdd"]     = d["hdd"]
        s["wind_ms"] = weather_map.get(d["date"], 0.0)
        scored.append(s)

    winds  = [s["wind_ms"] for s in scored]
    scored = flag_anomalous_days(scored, winds)

    heating_scored = [s for s in scored if s["score"] is not None]
    total_hdd  = sum(d["hdd"] for d in winter_days if d["hdd"] > 0)
    total_gas  = sum(d["gas_kwh"] for d in winter_days)
    kwh_per_hdd = total_gas / total_hdd if total_hdd > 0 else 0.0
    bench = benchmark_percentile(kwh_per_hdd, meta["property_type"], meta["build_era"])

    mean_score   = sum(s["score"] for s in heating_scored) / max(len(heating_scored), 1)
    alert_count  = sum(1 for s in scored if s.get("sustained_alert"))

    print(f"  M{meter_id}: R²={r_sq:.2f}  mean_score={mean_score:.0f}  "
          f"alert_days={alert_count}  "
          f"benchmark={bench['band']} ({bench.get('percentile', '-')}th pct)")

    rows = []
    for s in scored:
        rows.append({
            "meter_id":    meter_id,
            "date":        s["date"],
            "hdd":         s["hdd"],
            "expected_kwh": s.get("expected_kwh", ""),
            "actual_kwh":  s.get("actual_kwh", ""),
            "score":       s.get("score", ""),
            "z_score":     s.get("z_score", ""),
            "anomalous":   s.get("anomalous", ""),
            "anomaly_type": s.get("anomaly_type", ""),
            "sustained_alert": s.get("sustained_alert", ""),
        })
    return rows


def main():
    print("Service #6 — Heating Efficiency Scoring")
    print(f"  Regression window: {REGRESSION_START} to {REGRESSION_END}")
    print(f"  Scoring window:    {WINTER_START} to {WINTER_END}\n")

    all_rows = []
    for meter_id in sorted(METERS):
        all_rows.extend(analyse_meter(meter_id))

    fields = ["meter_id", "date", "hdd", "expected_kwh", "actual_kwh",
              "score", "z_score", "anomalous", "anomaly_type", "sustained_alert"]
    with open(OUT_FILE, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(all_rows)

    print(f"\nWrote {len(all_rows)} rows to {OUT_FILE}")


if __name__ == "__main__":
    main()

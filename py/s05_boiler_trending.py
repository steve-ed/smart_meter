"""
Service #5 — Boiler Efficiency Trending.

Compares baseline heating season kWh/HDD against the past 28 days.
Alerts if recent efficiency is >15% worse than baseline.

Run: python py/s05_boiler_trending.py
Outputs: data/s05_boiler_trending.csv
"""

import csv
from datetime import date, timedelta

from config import METERS, REGRESSION_START, REGRESSION_END
from tier2_lib import build_daily_gas_hdd

OUT_FILE               = "data/s05_boiler_trending.csv"
TREND_ALERT_THRESHOLD  = 0.15
TREND_HIGH_THRESHOLD   = 0.25
MIN_BASELINE_HDD_DAYS  = 60
MIN_RECENT_HDD_DAYS    = 20


def _series_slope(series: list[float]) -> float:
    n = len(series)
    if n < 2:
        return 0.0
    x_mean = (n - 1) / 2.0
    y_mean = sum(series) / n
    num = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(series))
    den = sum((i - x_mean) ** 2 for i in range(n))
    return num / den if den > 0 else 0.0


def classify_trend(weekly_kwh_per_hdd: list[float]) -> str:
    n = len(weekly_kwh_per_hdd)
    if n < 8:
        return "insufficient_data"
    first  = weekly_kwh_per_hdd[:n // 2]
    second = weekly_kwh_per_hdd[n // 2:]
    first_mean  = sum(first) / len(first)
    second_mean = sum(second) / len(second)
    step_ratio  = second_mean / first_mean if first_mean > 0 else 1.0
    # step_change: large jump between halves, each half individually flat
    first_flat  = abs(_series_slope(first)) < 0.05
    second_flat = abs(_series_slope(second)) < 0.05
    if step_ratio > 1.20 and first_flat and second_flat:
        return "step_change"
    # gradual_trend: relative slope (fraction per week) above threshold
    y_mean = sum(weekly_kwh_per_hdd) / n
    slope  = _series_slope(weekly_kwh_per_hdd)
    if y_mean > 0 and slope / y_mean > 0.008:
        return "gradual_trend"
    return "stable"


def detect_boiler_degradation(baseline_records: list[tuple[float, float]],
                               recent_records:   list[tuple[float, float]]) -> dict:
    if (len(baseline_records) < MIN_BASELINE_HDD_DAYS or
            len(recent_records) < MIN_RECENT_HDD_DAYS):
        return {"status": "insufficient_data"}
    base_kwh_per_hdd   = (sum(g for _, g in baseline_records) /
                           sum(h for h, _ in baseline_records))
    recent_kwh_per_hdd = (sum(g for _, g in recent_records) /
                           sum(h for h, _ in recent_records))
    pct = (recent_kwh_per_hdd - base_kwh_per_hdd) / base_kwh_per_hdd * 100
    alert    = pct > TREND_ALERT_THRESHOLD * 100
    severity = ("HIGH"   if pct > TREND_HIGH_THRESHOLD * 100 else
                "MEDIUM" if alert else None)
    return {
        "status":               "ok",
        "baseline_kwh_per_hdd": round(base_kwh_per_hdd, 2),
        "recent_kwh_per_hdd":   round(recent_kwh_per_hdd, 2),
        "pct_change":           round(pct, 1),
        "alert":                alert,
        "alert_severity":       severity,
    }


def _weekly_series(heating_days: list[dict]) -> list[float]:
    """Group HDD-days into 4-week bins and return kWh/HDD per bin."""
    if not heating_days:
        return []
    from_d = date.fromisoformat(heating_days[0]["date"])
    bins: dict[int, list[tuple[float, float]]] = {}
    for d in heating_days:
        week = (date.fromisoformat(d["date"]) - from_d).days // 7
        bins.setdefault(week, []).append((d["hdd"], d["gas_kwh"]))
    result = []
    for w in sorted(bins):
        pairs = bins[w]
        total_hdd = sum(h for h, _ in pairs)
        total_gas = sum(g for _, g in pairs)
        if total_hdd > 0:
            result.append(total_gas / total_hdd)
    return result


def analyse_meter(meter_id: int) -> dict:
    all_days = build_daily_gas_hdd(meter_id, REGRESSION_START, REGRESSION_END)
    heating  = [d for d in all_days if d["hdd"] > 0.5]

    today     = date.today()
    cutoff    = (today - timedelta(days=28)).isoformat()
    baseline  = [(d["hdd"], d["gas_kwh"]) for d in heating
                 if d["date"] < cutoff]
    recent    = [(d["hdd"], d["gas_kwh"]) for d in heating
                 if d["date"] >= cutoff]

    result  = detect_boiler_degradation(baseline, recent)
    weekly  = _weekly_series([d for d in heating if d["date"] < cutoff])
    trend   = classify_trend(weekly)

    result["meter_id"]   = meter_id
    result["trend_type"] = trend

    if result.get("status") == "insufficient_data":
        print(f"  M{meter_id}: insufficient data")
    else:
        alert_str = f"ALERT ({result['alert_severity']})" if result["alert"] else "ok"
        print(f"  M{meter_id}: baseline={result['baseline_kwh_per_hdd']} "
              f"recent={result['recent_kwh_per_hdd']} "
              f"change={result['pct_change']:+.1f}%  {alert_str}  [{trend}]")
    return result


def main():
    print("Service #5 — Boiler Efficiency Trending\n")
    fields = ["meter_id", "baseline_kwh_per_hdd", "recent_kwh_per_hdd",
              "pct_change", "alert", "alert_severity", "trend_type", "status"]
    rows = []
    for meter_id in sorted(METERS):
        r = analyse_meter(meter_id)
        rows.append({f: r.get(f, "") for f in fields})

    with open(OUT_FILE, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"\nWrote {len(rows)} rows to {OUT_FILE}")


if __name__ == "__main__":
    main()

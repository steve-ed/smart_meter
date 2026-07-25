"""
Service #7 — Degree-Day Budget Forecasting.

Auto-computes a monthly gas budget from the past 12 months' average spend,
then projects the current month's remaining spend using forecast temperatures.

Run: python py/s07_budget_forecast.py
Outputs: data/s07_budget_forecast.csv
"""

import csv
import calendar
from datetime import date, timedelta

from config import GAS_RATE_P_KWH, METERS, REGRESSION_START, REGRESSION_END
from tier2_lib import (
    build_daily_gas_hdd,
    fit_hdd_regression,
    load_weather,
    daily_hdd,
)

OUT_FILE = "data/s07_budget_forecast.csv"

CLIMATOLOGICAL_MEAN_C = {
    1: 4.2, 2: 4.5, 3: 6.5, 4: 9.0, 5: 12.0, 6: 15.0,
    7: 17.0, 8: 16.8, 9: 14.0, 10: 10.5, 11: 7.0, 12: 4.8,
}
FORECAST_UNCERTAINTY_C = 2.0


def compute_monthly_budget(monthly_spend_gbp: list[float]) -> float:
    return sum(monthly_spend_gbp) / len(monthly_spend_gbp)


def project_kwh_for_day(hdd: float, slope: float, intercept: float) -> float:
    return slope * hdd + intercept


def thermostat_nudge(budget_gap_gbp: float,
                      remaining_days: int,
                      gas_rate_p_per_kwh: float,
                      slope: float) -> dict:
    if remaining_days == 0 or slope == 0:
        return {}
    gap_kwh = budget_gap_gbp * 100 / gas_rate_p_per_kwh
    reduction = gap_kwh / (slope * remaining_days)
    return {
        "thermostat_reduction_c": round(reduction, 1),
        "budget_gap_kwh":         round(gap_kwh, 1),
        "days_to_implement_by":   remaining_days,
    }


def _monthly_spend(all_days: list[dict]) -> dict[str, float]:
    monthly: dict[str, float] = {}
    for d in all_days:
        month_key = d["date"][:7]
        spend = d["gas_kwh"] * GAS_RATE_P_KWH / 100
        monthly[month_key] = monthly.get(month_key, 0.0) + spend
    return monthly


def _forecast_temp_map() -> dict[str, tuple[float, float]]:
    result = {}
    for r in load_weather():
        if r["is_forecast"] == 1:
            d = r["timestamp"][:10]
            result.setdefault(d, []).append(r["temp_c"])
    return {d: (sum(v) / len(v), FORECAST_UNCERTAINTY_C) for d, v in result.items()}


def analyse_meter(meter_id: int) -> dict:
    today = date.today()

    all_days = build_daily_gas_hdd(meter_id, REGRESSION_START, REGRESSION_END)

    monthly_spend = _monthly_spend(all_days)
    twelve_months = sorted(monthly_spend)[-12:]
    if not twelve_months:
        print(f"  M{meter_id}: no monthly data")
        return {"meter_id": meter_id, "status": "insufficient_data"}
    budget = compute_monthly_budget([monthly_spend[m] for m in twelve_months])

    heating_days = [(d["hdd"], d["gas_kwh"]) for d in all_days if d["hdd"] > 0.5]
    slope, intercept, r_sq = fit_hdd_regression(heating_days)

    month_start = today.replace(day=1).isoformat()
    actual_so_far_kwh = sum(
        d["gas_kwh"] for d in all_days
        if month_start <= d["date"] <= today.isoformat()
    )
    actual_so_far_gbp = actual_so_far_kwh * GAS_RATE_P_KWH / 100

    days_in_month  = calendar.monthrange(today.year, today.month)[1]
    remaining_days = [
        today + timedelta(days=i)
        for i in range(1, days_in_month - today.day + 1)
    ]

    forecast_map = _forecast_temp_map()

    proj_central = proj_high = proj_low = 0.0
    for d in remaining_days:
        ds = d.isoformat()
        if ds in forecast_map:
            mean_t, std = forecast_map[ds]
        else:
            mean_t = CLIMATOLOGICAL_MEAN_C[d.month]
            std    = FORECAST_UNCERTAINTY_C
        hdd_c    = daily_hdd(mean_t)
        hdd_cold = daily_hdd(mean_t - std)
        hdd_warm = daily_hdd(mean_t + std)
        proj_central += project_kwh_for_day(hdd_c,    slope, intercept)
        proj_high    += project_kwh_for_day(hdd_cold, slope, intercept)
        proj_low     += project_kwh_for_day(hdd_warm, slope, intercept)

    total_c = actual_so_far_gbp + proj_central * GAS_RATE_P_KWH / 100
    total_h = actual_so_far_gbp + proj_high    * GAS_RATE_P_KWH / 100
    total_l = actual_so_far_gbp + proj_low     * GAS_RATE_P_KWH / 100
    gap     = total_c - budget
    exceed  = total_h > budget

    nudge = {}
    if exceed:
        nudge = thermostat_nudge(max(gap, 0), len(remaining_days),
                                  GAS_RATE_P_KWH, slope)

    print(f"  M{meter_id}: budget=£{budget:.2f}  "
          f"actual=£{actual_so_far_gbp:.2f}  "
          f"proj=£{total_c:.2f} [£{total_l:.2f}–£{total_h:.2f}]  "
          f"gap={gap:+.2f}  exceed={exceed}"
          + (f"  nudge={nudge['thermostat_reduction_c']}°C" if nudge else ""))

    return {
        "meter_id":            meter_id,
        "monthly_budget_gbp":  round(budget, 2),
        "actual_so_far_gbp":   round(actual_so_far_gbp, 2),
        "projected_total_gbp": round(total_c, 2),
        "projected_high_gbp":  round(total_h, 2),
        "projected_low_gbp":   round(total_l, 2),
        "budget_gap_gbp":      round(gap, 2),
        "will_exceed":         exceed,
        "thermostat_reduction_c": nudge.get("thermostat_reduction_c", ""),
        "days_remaining":      len(remaining_days),
        "status":              "ok",
    }


def main():
    print("Service #7 — Degree-Day Budget Forecasting\n")
    fields = ["meter_id", "monthly_budget_gbp", "actual_so_far_gbp",
              "projected_total_gbp", "projected_high_gbp", "projected_low_gbp",
              "budget_gap_gbp", "will_exceed", "thermostat_reduction_c",
              "days_remaining", "status"]
    rows = []
    for meter_id in sorted(METERS):
        rows.append(analyse_meter(meter_id))

    with open(OUT_FILE, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows([{f: r.get(f, "") for f in fields} for r in rows])
    print(f"\nWrote {len(rows)} rows to {OUT_FILE}")


if __name__ == "__main__":
    main()

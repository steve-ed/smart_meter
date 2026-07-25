"""
Service #2 — Battery Size Optimisation.

Wraps battery_simulator.simulate_day to sweep battery capacities and find
the optimal size by shortest payback period.

Run: python py/s02_battery_sizing.py
Outputs: data/s02_battery_sizing.csv
"""

import csv
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from battery_simulator import simulate_day
from config import METERS, ELEC_METERS
from tier1_lib import load_electricity, load_tariff_rates

OUT_FILE         = "data/s02_battery_sizing.csv"
CAPACITIES_KWH   = [2.0, 4.0, 5.0, 7.0, 10.0, 13.5]
COST_PER_KWH_GBP = 700
MAX_PAYBACK_YRS  = 15
DISCOUNT_RATE    = 0.035
NPV_YEARS        = 10


def build_daily_arrays(readings: list[dict],
                        period_rates: dict[int, float]) -> list[tuple[list, list]]:
    """
    Group readings by date into (consumption_48, tariff_48) pairs.
    Skips days with fewer than 48 readings.
    """
    by_date: dict[str, list] = {}
    for r in readings:
        d = r["timestamp"][:10]
        by_date.setdefault(d, []).append(r)

    arrays = []
    for d in sorted(by_date):
        day_rows = sorted(by_date[d], key=lambda r: r["period_index"])
        if len(day_rows) < 48:
            continue
        consumption_hh = [day_rows[p]["elec_kwh"] for p in range(48)]
        tariff_hh      = [period_rates.get(p, 24.0) for p in range(48)]
        arrays.append((consumption_hh, tariff_hh))
    return arrays


def npv(annual_saving: float, upfront_cost: float,
        rate: float = DISCOUNT_RATE, years: int = NPV_YEARS) -> float:
    pv = sum(annual_saving / (1 + rate) ** t for t in range(1, years + 1))
    return round(pv - upfront_cost, 2)


def find_recommended(curve: list[dict]) -> dict | None:
    """Return the entry with shortest finite payback <= MAX_PAYBACK_YRS, or None."""
    eligible = [r for r in curve
                if r["payback_years"] != float("inf") and r["payback_years"] <= MAX_PAYBACK_YRS]
    if not eligible:
        return None
    return min(eligible, key=lambda r: r["payback_years"])


def analyse_meter(meter_id: int) -> list[dict]:
    mpan = ELEC_METERS[meter_id]
    readings = load_electricity(meter_id)
    if not readings:
        print(f"  M{meter_id}: no electricity data")
        return []

    period_rates, _ = load_tariff_rates(mpan)
    daily_arrays = build_daily_arrays(readings, period_rates)
    n_days = len(daily_arrays)
    if n_days < 7:
        print(f"  M{meter_id}: insufficient data ({n_days} complete days)")
        return []

    curve = []
    for cap in CAPACITIES_KWH:
        max_c_rate  = min(cap * 0.5, 3.6) / cap
        total_saving_p = 0.0
        for cons_hh, tariff_hh in daily_arrays:
            result = simulate_day(
                cons_hh, tariff_hh, cap,
                round_trip_efficiency=0.92,
                max_c_rate=max_c_rate,
                min_soc=0.10,
            )
            total_saving_p += result["daily_saving_p"]

        annual_saving_gbp = round(total_saving_p / 100 * 365 / n_days, 2)
        installed_cost    = cap * COST_PER_KWH_GBP
        payback           = (installed_cost / annual_saving_gbp
                             if annual_saving_gbp > 0 else float("inf"))
        npv_val           = npv(annual_saving_gbp, installed_cost)

        curve.append({
            "capacity_kwh":       cap,
            "installed_cost_gbp": installed_cost,
            "annual_saving_gbp":  annual_saving_gbp,
            "payback_years":      round(payback, 1) if payback != float("inf") else float("inf"),
            "npv_10yr_gbp":       npv_val,
        })

    recommended = find_recommended(curve)
    rec_cap = recommended["capacity_kwh"] if recommended else None

    for entry in curve:
        entry["recommended"] = (entry["capacity_kwh"] == rec_cap)

    print(f"  M{meter_id}: {n_days} days  "
          + (f"recommended={rec_cap}kWh  "
             f"saving=£{recommended['annual_saving_gbp']}/yr  "
             f"payback={recommended['payback_years']}yr"
             if recommended else "no viable capacity found"))

    return [{"meter_id": meter_id, **e} for e in curve]


def main():
    print("Service #2 — Battery Size Optimisation\n")
    all_rows = []
    for meter_id in sorted(METERS):
        all_rows.extend(analyse_meter(meter_id))

    fields = ["meter_id", "capacity_kwh", "installed_cost_gbp",
              "annual_saving_gbp", "payback_years", "npv_10yr_gbp", "recommended"]
    with open(OUT_FILE, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows([{f: r.get(f, "") for f in fields} for r in all_rows])
    print(f"\nWrote {len(all_rows)} rows to {OUT_FILE}")


if __name__ == "__main__":
    main()

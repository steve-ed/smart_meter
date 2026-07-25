"""
Service #1 — E.ON Tariff Comparison.

For each meter, compares actual electricity spend against E.ON Next Fixed,
Drive, and Flex products. Ranks by projected annual cost.

Run: python py/s01_tariff_matching.py
Outputs: data/s01_tariff_matching.csv
"""

import csv
import json

from config import METERS, ELEC_METERS
from tier1_lib import (
    load_electricity,
    load_tariff_rates,
    build_weekly_profile,
    consumption_shape,
    annual_cost_for_tariff,
)

OUT_FILE     = "data/s01_tariff_matching.csv"
TARIFFS_FILE = "data/eon_tariffs.json"
TOO_CLOSE_GBP = 20.0


def rank_tariffs(readings: list[dict],
                 period_rates: dict[int, float],
                 standing_p_day: float,
                 eon_products: list[dict]) -> list[dict]:
    """
    Rank E.ON products by projected annual cost vs current tariff.
    Returns list of result dicts sorted cheapest-first.
    """
    # Current (Flex / actual) cost — compute directly from period_rates
    days = len(set(r["timestamp"][:10] for r in readings))
    unit_cost_p = sum(r["elec_kwh"] * period_rates.get(r["period_index"], 0.0)
                      for r in readings)
    scale = 365 / days if days < 365 else 1.0
    unit_annual_p = unit_cost_p * scale
    standing_annual_p = standing_p_day * 365
    current_gbp = round((unit_annual_p + standing_annual_p) / 100, 2)
    current = {
        "total_cost_gbp":    current_gbp,
        "unit_cost_gbp":     round(unit_annual_p / 100, 2),
        "standing_cost_gbp": round(standing_annual_p / 100, 2),
        "days_in_sample":    days,
    }

    results = []
    for product in eon_products:
        if product["product_type"] == "actual":
            cost = current
        else:
            bands = product["bands"]
            sc    = product["standing_p_day"]
            cost  = annual_cost_for_tariff(readings, bands, sc)

        saving = current_gbp - cost["total_cost_gbp"]
        results.append({
            "product":               product["name"],
            "product_type":          product["product_type"],
            "annual_cost_gbp":       cost["total_cost_gbp"],
            "saving_vs_current_gbp": round(saving, 2),
            "saving_pct":            round(saving / current_gbp * 100, 1) if current_gbp > 0 else 0.0,
            "days_in_sample":        cost["days_in_sample"],
        })

    results.sort(key=lambda x: x["annual_cost_gbp"])
    for i, r in enumerate(results):
        r["rank"] = i + 1
    return results


def flag_too_close(ranked: list[dict], threshold_gbp: float = TOO_CLOSE_GBP) -> list[dict]:
    """Mark too_close=True on all entries if the best saving from alternatives is within threshold_gbp."""
    alternatives = [r for r in ranked if r["product_type"] != "actual"]
    best_saving = alternatives[0]["saving_vs_current_gbp"] if alternatives else 0.0
    close = best_saving < threshold_gbp
    for r in ranked:
        r["too_close"] = close
    return ranked


def analyse_meter(meter_id: int, eon_products: list[dict]) -> list[dict]:
    mpan = ELEC_METERS[meter_id]
    readings = load_electricity(meter_id)
    if not readings:
        print(f"  M{meter_id}: no electricity data")
        return []

    period_rates, standing_p_day = load_tariff_rates(mpan)
    profile = build_weekly_profile(readings)
    shape   = consumption_shape(profile)

    ranked = rank_tariffs(readings, period_rates, standing_p_day, eon_products)
    ranked = flag_too_close(ranked)

    best = ranked[0]
    print(f"  M{meter_id}: best={best['product']}  "
          f"saving=£{best['saving_vs_current_gbp']:+.2f}  "
          f"night_frac={shape['night_fraction']:.2f}  "
          f"annual_kwh={shape['annual_kwh_estimate']:.0f}")

    rows = []
    for r in ranked:
        rows.append({
            "meter_id":              meter_id,
            "product":               r["product"],
            "product_type":          r["product_type"],
            "annual_cost_gbp":       r["annual_cost_gbp"],
            "saving_vs_current_gbp": r["saving_vs_current_gbp"],
            "saving_pct":            r["saving_pct"],
            "night_fraction":        round(shape["night_fraction"], 4),
            "too_close":             r["too_close"],
            "rank":                  r["rank"],
        })
    return rows


def main():
    print("Service #1 — E.ON Tariff Comparison\n")
    with open(TARIFFS_FILE) as f:
        eon_products = json.load(f)

    all_rows = []
    for meter_id in sorted(METERS):
        all_rows.extend(analyse_meter(meter_id, eon_products))

    fields = ["meter_id", "product", "product_type", "annual_cost_gbp",
              "saving_vs_current_gbp", "saving_pct", "night_fraction",
              "too_close", "rank"]
    with open(OUT_FILE, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(all_rows)
    print(f"\nWrote {len(all_rows)} rows to {OUT_FILE}")


if __name__ == "__main__":
    main()

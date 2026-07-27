"""
Service #1 — E.ON Tariff Comparison.

For each meter, compares actual electricity spend against E.ON Next Fixed,
Drive, and Flex products. Ranks by projected annual cost.

Run: python py/s01_tariff_matching.py
Outputs: data/s01_tariff_matching.csv
"""

import csv
import json

from config import METERS, ELEC_METERS, ELEC_RATE_P_KWH, SEG_RATE_P_KWH
from tier1_lib import (
    load_electricity,
    load_solar_generation,
    load_tariff_rates,
    build_weekly_profile,
    consumption_shape,
    annual_cost_for_tariff,
    compute_annual_export,
)

OUT_FILE     = "data/s01_tariff_matching.csv"
TARIFFS_FILE = "data/eon_tariffs.json"
TOO_CLOSE_GBP = 20.0


def _period_to_time(period: int) -> str:
    h, m = divmod(period * 30, 60)
    return f"{h:02d}:{m:02d}"


def _summarise_rates(period_rates: dict[int, float]) -> list[tuple[str, str, float]]:
    """Return list of (start_time, end_time, rate) bands by grouping consecutive equal rates."""
    bands = []
    prev_rate = None
    start_p = 0
    for p in range(48):
        rate = period_rates.get(p, ELEC_RATE_P_KWH)
        if rate != prev_rate:
            if prev_rate is not None:
                bands.append((_period_to_time(start_p), _period_to_time(p - 1), prev_rate))
            start_p = p
            prev_rate = rate
    if prev_rate is not None:
        bands.append((_period_to_time(start_p), _period_to_time(47), prev_rate))
    return bands


def _format_rates(period_rates: dict[int, float], standing_p_day: float) -> str:
    bands = _summarise_rates(period_rates)
    if len(bands) == 1:
        rate_str = f"{bands[0][2]}p/kWh all-day"
    else:
        rate_str = ", ".join(f"{r}p {s}–{e}" for s, e, r in bands)
    standing_str = f"{round(standing_p_day, 1)}p/day standing" if standing_p_day else "no standing charge"
    return f"{rate_str} | {standing_str}"


def _format_product_rates(product: dict) -> str:
    bands = product["bands"]
    standing = product["standing_p_day"]
    if len(bands) == 1:
        rate_str = f"{bands[0]['rate_p_per_kwh']}p/kWh all-day"
    else:
        rate_str = ", ".join(
            f"{b['rate_p_per_kwh']}p {_period_to_time(b['start_period'])}–{_period_to_time(b['end_period'])}"
            for b in bands
        )
    standing_str = f"{standing}p/day standing" if standing else "no standing charge"
    return f"{rate_str} | {standing_str}"


def current_annual_cost(readings: list[dict],
                         period_rates: dict[int, float],
                         standing_p_day: float) -> dict:
    days = len(set(r["timestamp"][:10] for r in readings))
    unit_cost_p = sum(r["elec_kwh"] * period_rates.get(r["period_index"], 0.0)
                      for r in readings)
    scale = 365 / days
    unit_annual_p     = unit_cost_p * scale
    standing_annual_p = standing_p_day * 365
    return {
        "total_cost_gbp":    round((unit_annual_p + standing_annual_p) / 100, 2),
        "unit_cost_gbp":     round(unit_annual_p / 100, 2),
        "standing_cost_gbp": round(standing_annual_p / 100, 2),
        "days_in_sample":    days,
    }


def rank_alternatives(readings: list[dict],
                       current_gbp: float,
                       eon_products: list[dict]) -> list[dict]:
    """
    Rank non-actual E.ON products by saving vs current tariff, best saving first.
    Excludes the 'actual' product — that is the reference, not an alternative.
    """
    results = []
    for product in eon_products:
        if product["product_type"] == "actual":
            continue
        cost   = annual_cost_for_tariff(readings, product["bands"], product["standing_p_day"])
        saving = current_gbp - cost["total_cost_gbp"]
        results.append({
            "product":               product["name"],
            "type":                  product["product_type"],
            "annual_cost_gbp":       cost["total_cost_gbp"],
            "saving_vs_current_gbp": round(saving, 2),
            "saving_pct":            round(saving / current_gbp * 100, 1) if current_gbp > 0 else 0.0,
            "days_in_sample":        cost["days_in_sample"],
        })

    # Sort by saving descending — best saving (most positive) first
    results.sort(key=lambda x: -x["saving_vs_current_gbp"])
    for i, r in enumerate(results):
        r["rank"] = i + 1
    return results


def flag_too_close(ranked: list[dict], threshold_gbp: float = TOO_CLOSE_GBP) -> list[dict]:
    """
    Mark too_close=True only when the best saving is positive but below threshold.
    False when no alternative saves money, or when saving comfortably exceeds threshold.
    """
    best_saving = ranked[0]["saving_vs_current_gbp"] if ranked else 0.0
    close = 0 < best_saving < threshold_gbp
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
    is_default = all(v == ELEC_RATE_P_KWH for v in period_rates.values()) and standing_p_day == 0.0

    profile  = build_weekly_profile(readings)
    shape    = consumption_shape(profile)
    current  = current_annual_cost(readings, period_rates, standing_p_day)
    current_gbp = current["total_cost_gbp"]

    ranked = rank_alternatives(readings, current_gbp, eon_products)
    ranked = flag_too_close(ranked)

    gen_rows     = load_solar_generation(meter_id)
    export       = compute_annual_export(readings, gen_rows)
    seg_earnings = round(export["annual_export_kwh"] * SEG_RATE_P_KWH / 100, 2)

    best = ranked[0] if ranked else None
    best_saving = best["saving_vs_current_gbp"] if best else 0.0
    print(f"  M{meter_id}: current=£{current_gbp:.2f}  "
          f"best_saving=£{best_saving:+.2f}  "
          f"night_frac={shape['night_fraction']:.2f}  "
          f"annual_kwh={shape['annual_kwh_estimate']:.0f}")

    actual = next((p for p in eon_products if p["product_type"] == "actual"), None)
    actual_name = actual["name"] if actual else "Current Tariff"

    suffix = " (default)" if is_default else ""
    rows = [{
        "meter_id":                meter_id,
        "product":                 actual_name,
        "type":                    f"actual{suffix}",
        "rates":                   _format_rates(period_rates, standing_p_day),
        "current_annual_cost_gbp": current_gbp,
        "annual_cost_gbp":         current_gbp,
        "saving_vs_current_gbp":   0.0,
        "saving_pct":              0.0,
        "night_fraction":          round(shape["night_fraction"], 4),
        "too_close":               False,
        "rank":                    0,
        "seg_earnings_gbp":        seg_earnings,
        "net_cost_gbp":            round(current_gbp - seg_earnings, 2),
    }]
    for r in ranked:
        product = next(p for p in eon_products if p["name"] == r["product"])
        rows.append({
            "meter_id":                meter_id,
            "product":                 r["product"],
            "type":                    r["type"],
            "rates":                   _format_product_rates(product),
            "current_annual_cost_gbp": current_gbp,
            "annual_cost_gbp":         r["annual_cost_gbp"],
            "saving_vs_current_gbp":   r["saving_vs_current_gbp"],
            "saving_pct":              r["saving_pct"],
            "night_fraction":          round(shape["night_fraction"], 4),
            "too_close":               r["too_close"],
            "rank":                    r["rank"],
            "seg_earnings_gbp":        seg_earnings,
            "net_cost_gbp":            round(r["annual_cost_gbp"] - seg_earnings, 2),
        })
    return rows


def main():
    print("Service #1 — E.ON Tariff Comparison\n")
    with open(TARIFFS_FILE) as f:
        eon_products = json.load(f)

    all_rows = []
    for meter_id in sorted(METERS):
        all_rows.extend(analyse_meter(meter_id, eon_products))

    fields = ["meter_id", "product", "type", "rates", "current_annual_cost_gbp",
              "annual_cost_gbp", "saving_vs_current_gbp", "saving_pct",
              "night_fraction", "too_close", "rank",
              "seg_earnings_gbp", "net_cost_gbp"]
    with open(OUT_FILE, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(all_rows)
    print(f"\nWrote {len(all_rows)} rows to {OUT_FILE}")


if __name__ == "__main__":
    main()

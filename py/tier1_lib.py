"""
Shared foundation for Tier 1 smart meter service scripts.
Not run directly — imported by s01_*.py through s04_*.py.
"""

import csv
import statistics
from datetime import datetime, timedelta

from config import ELEC_METERS, ELEC_CAP_KWH


def load_electricity(meter_id: int,
                     path: str = "data/consumption.csv") -> list[dict]:
    """
    Return half-hourly electricity rows for one meter, sorted by timestamp.
    Filters out readings above ELEC_CAP_KWH.
    """
    mpan = ELEC_METERS[meter_id]
    seen: set[str] = set()
    rows = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            if row["mpxn"] != mpan or row["utility"] != "electricity":
                continue
            ts = row["timestamp"]           # "YYYY-MM-DD HH:MM"
            if ts in seen:
                continue
            seen.add(ts)
            val = float(row["value"])
            if val > ELEC_CAP_KWH:
                continue
            dt = datetime.strptime(ts, "%Y-%m-%d %H:%M")
            rows.append({
                "timestamp":    ts,
                "elec_kwh":     round(val, 4),
                "weekday":      dt.weekday(),
                "period_index": dt.hour * 2 + dt.minute // 30,
            })
    return sorted(rows, key=lambda r: r["timestamp"])


def load_tariff_rates(mpan: str,
                      path: str = "data/tariff.csv") -> tuple[dict[int, float], float]:
    """
    Return (period_rates, standing_p_day) for the given MPAN.
    Uses the most recent unit_rate per period and the most recent standing_charge.
    period_rates: {period_index: rate_p_per_kwh}
    """
    unit_rows: dict[int, tuple[str, float]] = {}   # period -> (latest_ts, rate)
    standing_rows: list[tuple[str, float]] = []

    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            if row["mpan"] != mpan:
                continue
            if row["type"] == "unit_rate":
                ts     = row["timestamp"]           # "YYYY-MM-DD HH:MM"
                dt     = datetime.strptime(ts, "%Y-%m-%d %H:%M")
                period = dt.hour * 2 + dt.minute // 30
                rate   = float(row["value"])
                if period not in unit_rows or ts > unit_rows[period][0]:
                    unit_rows[period] = (ts, rate)
            elif row["type"] == "standing_charge":
                standing_rows.append((row["timestamp"], float(row["value"])))

    period_rates   = {p: v for p, (_, v) in unit_rows.items()}
    # CSV values are in £/day despite the unit label; convert to p/day
    standing_p_day = max(standing_rows, key=lambda x: x[0])[1] * 100 if standing_rows else 0.0
    return period_rates, standing_p_day


def build_weekly_profile(readings: list[dict],
                          weeks: int = 8) -> dict[tuple[int, int], float]:
    """
    {(weekday, period_index): median_elec_kwh} over the last `weeks` weeks.
    """
    if not readings:
        return {}
    if weeks < 9999 and "timestamp" in readings[-1]:
        cutoff_ts = readings[-1]["timestamp"]
        cutoff_dt = datetime.strptime(cutoff_ts, "%Y-%m-%d %H:%M")
        cutoff_dt -= timedelta(weeks=weeks)
        readings = [r for r in readings
                    if datetime.strptime(r["timestamp"], "%Y-%m-%d %H:%M") >= cutoff_dt]

    slots: dict[tuple[int, int], list[float]] = {}
    for r in readings:
        key = (r["weekday"], r["period_index"])
        slots.setdefault(key, []).append(r["elec_kwh"])

    return {slot: statistics.median(vals) for slot, vals in slots.items()}


def consumption_shape(weekly_profile: dict[tuple[int, int], float]) -> dict:
    """
    Compute shape metrics from a weekly profile.
    """
    total = sum(weekly_profile.values())
    if total == 0:
        return {
            "night_fraction":        0.0,
            "morning_fraction":      0.0,
            "evening_peak_fraction": 0.0,
            "annual_kwh_estimate":   0.0,
        }
    night   = sum(v for (_, p), v in weekly_profile.items() if  0 <= p <= 13)
    morning = sum(v for (_, p), v in weekly_profile.items() if 12 <= p <= 17)
    peak    = sum(v for (_, p), v in weekly_profile.items() if 32 <= p <= 41)
    return {
        "night_fraction":        round(night   / total, 4),
        "morning_fraction":      round(morning / total, 4),
        "evening_peak_fraction": round(peak    / total, 4),
        "annual_kwh_estimate":   round(total / 7 * 365, 1),
    }


def rate_for_period(bands: list[dict], period_index: int) -> float:
    """Return rate_p_per_kwh for the given period from a list of band dicts."""
    for band in bands:
        if band["start_period"] <= period_index <= band["end_period"]:
            return band["rate_p_per_kwh"]
    raise ValueError(f"Period {period_index} not covered by any band")


def annual_cost_for_tariff(readings: list[dict],
                            bands: list[dict],
                            standing_p_day: float) -> dict:
    """
    Compute annual electricity cost (unit + standing) for the given tariff bands.
    Scales to 365 days if sample is shorter.
    """
    days = len(set(r["timestamp"][:10] for r in readings))
    unit_cost_p = 0.0
    for r in readings:
        unit_cost_p += r["elec_kwh"] * rate_for_period(bands, r["period_index"])

    scale = 365 / days
    unit_annual_p     = unit_cost_p * scale
    standing_annual_p = standing_p_day * 365

    return {
        "total_cost_gbp":    round((unit_annual_p + standing_annual_p) / 100, 2),
        "unit_cost_gbp":     round(unit_annual_p / 100, 2),
        "standing_cost_gbp": round(standing_annual_p / 100, 2),
        "days_in_sample":    days,
    }

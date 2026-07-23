"""
Shared foundation for Tier 2 weather service scripts.
Not run directly — imported by s05_*.py through s10_*.py.
"""

import csv
import math
from datetime import date, datetime

from config import GAS_KWH_PER_M3, GAS_CAP_M3, METERS

# ---------------------------------------------------------------------------
# HDD constants
# ---------------------------------------------------------------------------

BASE_TEMP_C = 15.5   # UK Met Office standard base temperature

# ---------------------------------------------------------------------------
# HDD functions
# ---------------------------------------------------------------------------

def daily_hdd(mean_temp_c: float) -> float:
    return max(BASE_TEMP_C - mean_temp_c, 0.0)


def period_hdd(temp_c: float) -> float:
    return max(BASE_TEMP_C - temp_c, 0.0) / 48


def effective_temp(temp_c: float, wind_speed_ms: float) -> float:
    if wind_speed_ms <= 2.0:
        return temp_c
    adjustment = (wind_speed_ms - 2.0) / 3.0 * 0.5
    return temp_c - adjustment


# ---------------------------------------------------------------------------
# HDD regression
# ---------------------------------------------------------------------------

def fit_hdd_regression(records: list[tuple[float, float]]) -> tuple[float, float, float]:
    """
    OLS fit on [(hdd, gas_kwh)] pairs.
    Returns (slope, intercept, r_squared).
    Clamps slope and intercept to >= 0.
    """
    n = len(records)
    if n < 2:
        return 0.0, 0.0, 0.0
    sx  = sum(r[0] for r in records)
    sy  = sum(r[1] for r in records)
    sxx = sum(r[0] ** 2 for r in records)
    sxy = sum(r[0] * r[1] for r in records)
    denom = n * sxx - sx * sx
    if abs(denom) < 1e-9:
        return 0.0, max(sy / n, 0.0), 0.0
    slope     = (n * sxy - sx * sy) / denom
    intercept = (sy - slope * sx) / n
    slope     = max(slope, 0.0)
    intercept = max(intercept, 0.0)
    y_mean = sy / n
    ss_tot = sum((r[1] - y_mean) ** 2 for r in records)
    ss_res = sum((r[1] - (slope * r[0] + intercept)) ** 2 for r in records)
    r_sq   = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return slope, intercept, r_sq


# ---------------------------------------------------------------------------
# Period utilities
# ---------------------------------------------------------------------------

def period_to_time(period_index: int) -> str:
    hour   = period_index // 2
    minute = (period_index % 2) * 30
    return f"{hour:02d}:{minute:02d}"


def time_to_period(hour: int, minute: int) -> int:
    return hour * 2 + minute // 30


# ---------------------------------------------------------------------------
# Peer benchmarks — kWh/HDD by (property_type, build_era)
# Source: NEED dataset (BEIS), values from docs/tier2_weather.md
# ---------------------------------------------------------------------------

UK_BENCHMARKS: dict[tuple[str, str], tuple[float, float, float]] = {
    # key: (median kWh/HDD, p25, p75)
    ("detached",   "pre_1945"):  (55.0, 42.0, 72.0),
    ("detached",   "1945_1980"): (42.0, 33.0, 54.0),
    ("detached",   "post_1980"): (30.0, 22.0, 40.0),
    ("semi",       "pre_1945"):  (40.0, 31.0, 52.0),
    ("semi",       "1945_1980"): (32.0, 25.0, 42.0),
    ("semi",       "post_1980"): (23.0, 17.0, 30.0),
    ("terraced",   "pre_1945"):  (35.0, 27.0, 46.0),
    ("terraced",   "1945_1980"): (28.0, 21.0, 37.0),
    ("terraced",   "post_1980"): (20.0, 15.0, 27.0),
    ("flat",       "pre_1945"):  (25.0, 18.0, 33.0),
    ("flat",       "1945_1980"): (20.0, 14.0, 28.0),
    ("flat",       "post_1980"): (14.0, 10.0, 19.0),
}


def benchmark_percentile(kwh_per_hdd: float,
                          property_type: str,
                          build_era: str) -> dict:
    key = (property_type, build_era)
    if key not in UK_BENCHMARKS:
        return {"percentile": None, "reason": "no_benchmark_available"}
    median, p25, p75 = UK_BENCHMARKS[key]
    if kwh_per_hdd <= p25:
        pct = 25 * kwh_per_hdd / p25
    elif kwh_per_hdd <= median:
        pct = 25 + 25 * (kwh_per_hdd - p25) / (median - p25)
    elif kwh_per_hdd <= p75:
        pct = 50 + 25 * (kwh_per_hdd - median) / (p75 - median)
    else:
        pct = 75 + 25 * min((kwh_per_hdd - p75) / p75, 1.0)
    band = "efficient" if pct < 33 else "average" if pct < 67 else "inefficient"
    return {
        "household_kwh_per_hdd": round(kwh_per_hdd, 1),
        "peer_median_kwh_per_hdd": median,
        "percentile": round(pct, 0),
        "band": band,
    }


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

def load_weather(path: str = "data/weather.csv") -> list[dict]:
    """Return half-hourly weather rows sorted by timestamp."""
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["temp_c"]        = float(r["temp_c"])
        r["wind_speed_ms"] = float(r["wind_speed_ms"])
        r["is_forecast"]   = int(r["is_forecast"])
    return sorted(rows, key=lambda r: r["timestamp"])


def load_consumption(meter_id: int,
                     path: str = "data/consumption.csv") -> list[dict]:
    """
    Return half-hourly gas kWh rows for one meter, sorted by timestamp.
    Filters out readings above GAS_CAP_M3 (sentinel / error values).
    """
    mpxn = METERS[meter_id]
    rows = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            if row["mpxn"] != mpxn or row["utility"] != "gas":
                continue
            val_m3 = float(row["value"])
            if val_m3 > GAS_CAP_M3:
                continue
            rows.append({
                "timestamp": row["timestamp"],
                "gas_kwh":   round(val_m3 * GAS_KWH_PER_M3, 4),
            })
    return sorted(rows, key=lambda r: r["timestamp"])


def build_daily_gas_hdd(meter_id: int,
                         start: str,
                         end: str) -> list[dict]:
    """
    Aggregate half-hourly gas and weather to daily records between start and end (inclusive).
    Returns list of {"date": str, "hdd": float, "gas_kwh": float, "mean_temp_c": float}.
    Only includes days with >=40 gas readings and >=40 weather readings (guard against gaps).
    """
    weather_by_date: dict[str, list[float]] = {}
    for r in load_weather():
        d = r["timestamp"][:10]
        if start <= d <= end:
            weather_by_date.setdefault(d, []).append(r["temp_c"])

    gas: dict[str, float] = {}
    gas_count: dict[str, int] = {}
    for r in load_consumption(meter_id):
        d = r["timestamp"][:10]
        if start <= d <= end:
            gas[d] = gas.get(d, 0.0) + r["gas_kwh"]
            gas_count[d] = gas_count.get(d, 0) + 1

    result = []
    for d in sorted(weather_by_date):
        temps = weather_by_date[d]
        if len(temps) < 40 or gas_count.get(d, 0) < 40:
            continue
        mean_temp = sum(temps) / len(temps)
        hdd       = daily_hdd(mean_temp)
        result.append({
            "date":        d,
            "hdd":         round(hdd, 3),
            "gas_kwh":     round(gas.get(d, 0.0), 4),
            "mean_temp_c": round(mean_temp, 2),
        })
    return result

"""
Service #9 — Heating Pre-Warm Optimisation.

Learns when the boiler fires each morning from historical gas data and fits
a regression against 06:00 outdoor temperature. Uses today's forecast to
recommend tomorrow's optimal start time.

Run: python py/s09_prewarm.py
Outputs: data/s09_prewarm.csv
"""

import csv
import math
from datetime import datetime

from config import METERS, REGRESSION_START, REGRESSION_END
from tier2_lib import (
    load_consumption,
    load_weather,
    fit_hdd_regression,
    period_to_time,
)

OUT_FILE          = "data/s09_prewarm.csv"
BOILER_ON_KWH     = 0.15
MORNING_PERIODS   = range(0, 24)   # 00:00–12:00
MIN_R2            = 0.45
MIN_OBSERVATIONS  = 40
MAX_HISTORY       = 120
SMART_THERM_STD   = 2.0
SMART_THERM_MIN   = 20


def extract_boiler_start(daily_periods: list[tuple[int, float]]) -> int | None:
    for period, kwh in sorted(daily_periods):
        if period in MORNING_PERIODS and kwh >= BOILER_ON_KWH:
            return period
    return None


def is_smart_thermostat_present(observations: list[tuple[int, float]]) -> bool:
    if len(observations) < SMART_THERM_MIN:
        return False
    starts = [o[0] for o in observations]
    mean   = sum(starts) / len(starts)
    std    = math.sqrt(sum((s - mean) ** 2 for s in starts) / len(starts))
    return std < SMART_THERM_STD


def recommend_start_time(forecast_temp: float,
                           slope: float,
                           intercept: float,
                           target_period: int,
                           r_squared: float) -> dict:
    if r_squared < MIN_R2:
        return {"recommendation": None, "reason": "insufficient_pattern",
                "message": "Not enough consistent data to predict optimal start time yet."}
    predicted = int(round(slope * forecast_temp + intercept))
    predicted = max(0, min(predicted, target_period - 1))
    uncertainty = max(2, int(4 * (1 - r_squared)))
    return {
        "recommended_start_period": predicted,
        "recommended_start_time":   period_to_time(predicted),
        "target_period":            target_period,
        "forecast_temp_c":          round(forecast_temp, 1),
        "uncertainty_periods":      uncertainty,
        "message": (f"Turn heating on at {period_to_time(predicted)} "
                    f"({forecast_temp:.0f}°C forecast)."),
    }


def _build_observations(meter_id: int) -> list[tuple[int, float]]:
    consumption = load_consumption(meter_id)
    weather     = load_weather()

    temp_at_0600: dict[str, float] = {}
    for r in weather:
        if r["timestamp"][11:16] == "06:00":
            temp_at_0600[r["timestamp"][:10]] = r["temp_c"]

    by_date: dict[str, list[tuple[int, float]]] = {}
    for r in consumption:
        ts  = datetime.strptime(r["timestamp"], "%Y-%m-%d %H:%M")
        d   = r["timestamp"][:10]
        if d < REGRESSION_START or d > REGRESSION_END:
            continue
        per = ts.hour * 2 + ts.minute // 30
        by_date.setdefault(d, []).append((per, r["gas_kwh"]))

    obs = []
    for d in sorted(by_date):
        start = extract_boiler_start(by_date[d])
        if start is None or d not in temp_at_0600:
            continue
        obs.append((start, temp_at_0600[d]))

    return obs[-MAX_HISTORY:]


def _today_forecast_temp() -> float:
    from datetime import date
    today = date.today().isoformat()
    for r in load_weather():
        if r["timestamp"][:10] == today and r["timestamp"][11:16] == "06:00":
            return r["temp_c"]
    return 8.0


def analyse_meter(meter_id: int) -> dict:
    obs = _build_observations(meter_id)

    if is_smart_thermostat_present(obs):
        print(f"  M{meter_id}: smart thermostat detected — service suppressed")
        return {"meter_id": meter_id, "status": "smart_thermostat_detected",
                "smart_thermostat_detected": True}

    if len(obs) < MIN_OBSERVATIONS:
        print(f"  M{meter_id}: insufficient observations ({len(obs)})")
        return {"meter_id": meter_id, "status": "insufficient_data",
                "smart_thermostat_detected": False}

    records = [(temp, float(start)) for start, temp in obs]
    slope, intercept, r_sq = fit_hdd_regression(records)

    forecast_temp = _today_forecast_temp()
    target_period = 14   # 07:00 default

    result = recommend_start_time(forecast_temp, slope, intercept, target_period, r_sq)

    start_str = (f"start={result['recommended_start_time']} (±{result['uncertainty_periods']} periods)"
                 if result.get("recommended_start_time") else result.get("message", ""))
    print(f"  M{meter_id}: R²={r_sq:.2f}  obs={len(obs)}  forecast={forecast_temp:.1f}°C  {start_str}")

    return {
        "meter_id":                meter_id,
        "recommended_start_time":  result.get("recommended_start_time", ""),
        "recommended_start_period": result.get("recommended_start_period", ""),
        "forecast_temp_c":         forecast_temp,
        "r_squared":               round(r_sq, 3),
        "uncertainty_periods":     result.get("uncertainty_periods", ""),
        "smart_thermostat_detected": False,
        "status":                  "ok" if result.get("recommended_start_time") else "insufficient_pattern",
    }


def main():
    print("Service #9 — Heating Pre-Warm Optimisation\n")
    fields = ["meter_id", "recommended_start_time", "recommended_start_period",
              "forecast_temp_c", "r_squared", "uncertainty_periods",
              "smart_thermostat_detected", "status"]
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

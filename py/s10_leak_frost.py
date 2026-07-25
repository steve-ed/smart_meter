"""
Service #10 — Micro-Leak and Frost Detection.

Micro-leak: flags sustained above-baseline overnight gas consumption.
Frost: alerts when property appears vacant and sub-zero temps are forecast,
       or when boiler appears off during expected heating with frost incoming.

Run: python py/s10_leak_frost.py
Outputs: data/s10_leak_frost.csv
"""

import csv
from datetime import date, datetime, timedelta

from config import METERS
from tier2_lib import load_consumption, load_weather, daily_hdd

OUT_FILE = "data/s10_leak_frost.csv"

OVERNIGHT_PERIODS   = list(range(0, 8)) + list(range(44, 48))
SUMMER_MONTHS       = {5, 6, 7, 8, 9}
LEAK_MIN_SAMPLES    = 30
LEAK_THRESHOLD_MULT = 3.0
LEAK_ABS_MIN_KWH    = 0.05
LEAK_SUSTAINED      = 6
FROST_RISK_C        = 2.0
PIPE_BURST_C        = -3.0
VACANT_HOURS        = 12
BOILER_ON_KWH       = 0.15


def overnight_baseline_kwh(readings: list[tuple]) -> dict:
    """
    readings: list of (date, period_index, gas_kwh)
    Computes statistics from summer overnight periods.
    """
    vals = [kwh for d, p, kwh in readings
            if d.month in SUMMER_MONTHS and p in OVERNIGHT_PERIODS and kwh is not None]
    if len(vals) < LEAK_MIN_SAMPLES:
        return {"status": "insufficient_data"}
    vals.sort()
    n = len(vals)
    return {
        "median_kwh":   vals[n // 2],
        "p95_kwh":      vals[int(n * 0.95)],
        "p99_kwh":      vals[int(n * 0.99)],
        "sample_count": n,
    }


def detect_gas_leak(overnight_readings: list[float], baseline: dict) -> dict:
    threshold = max(baseline["median_kwh"] * LEAK_THRESHOLD_MULT, LEAK_ABS_MIN_KWH)
    above     = [v >= threshold for v in overnight_readings]
    consec = max_consec = 0
    for flag in above:
        consec = consec + 1 if flag else 0
        max_consec = max(max_consec, consec)
    alert     = max_consec >= LEAK_SUSTAINED
    above_vals = [v for v in overnight_readings if v >= threshold]
    mean_excess = ((sum(v - baseline["median_kwh"] for v in above_vals) / len(above_vals))
                   if above_vals else 0.0)
    return {
        "alert":                   alert,
        "max_consecutive_periods": max_consec,
        "threshold_kwh":           round(threshold, 4),
        "mean_excess_kwh":         round(mean_excess, 4),
        "annualised_waste_kwh":    round(mean_excess * len(OVERNIGHT_PERIODS) * 365, 0) if alert else 0,
    }


def frost_alert(recent_gas_kwh: list[float],
                 overnight_forecast_low_c: float,
                 forecast_min_period: int) -> dict:
    if overnight_forecast_low_c >= FROST_RISK_C:
        return {"alert": False}
    vacant = all(g < 0.05 for g in recent_gas_kwh)
    if not vacant:
        return {"alert": False, "reason": "heating_has_been_active"}
    severity = "CRITICAL" if overnight_forecast_low_c < PIPE_BURST_C else "HIGH"
    return {
        "alert":               True,
        "severity":            severity,
        "forecast_low_c":      round(overnight_forecast_low_c, 1),
        "forecast_min_period": forecast_min_period,
        "action": "Set heating to minimum 10°C or ask neighbour to check property.",
    }


def heating_failure_frost_alert(expected_heating: bool,
                                  actual_gas_kwh: float,
                                  outdoor_temp_c: float,
                                  forecast_low_c: float) -> dict:
    boiler_absent = actual_gas_kwh < BOILER_ON_KWH
    if not (expected_heating and boiler_absent and forecast_low_c < FROST_RISK_C):
        return {"alert": False}
    return {
        "alert":          True,
        "severity":       "HIGH",
        "alert_type":     "heating_failure_with_frost_risk",
        "outdoor_temp_c": round(outdoor_temp_c, 1),
        "forecast_low_c": round(forecast_low_c, 1),
        "action":         "Boiler appears off. Check boiler pressure and power before overnight frost.",
    }


def _to_readings(consumption_rows: list[dict]) -> list[tuple]:
    result = []
    for r in consumption_rows:
        ts = datetime.strptime(r["timestamp"], "%Y-%m-%d %H:%M")
        period = ts.hour * 2 + ts.minute // 30
        result.append((ts.date(), period, r["gas_kwh"]))
    return result


def _recent_hourly_gas(consumption_rows: list[dict], hours: int = 12) -> list[float]:
    now   = datetime.now()
    cutoff = now - timedelta(hours=hours)
    by_hour: dict[int, float] = {}
    for r in consumption_rows:
        ts = datetime.strptime(r["timestamp"], "%Y-%m-%d %H:%M")
        if ts >= cutoff:
            h = ts.hour
            by_hour[h] = by_hour.get(h, 0.0) + r["gas_kwh"]
    return [by_hour.get(h, 0.0) for h in range(hours)]


def _forecast_overnight_low(weather_rows: list[dict]) -> tuple[float, int]:
    tonight = [r for r in weather_rows
               if r["is_forecast"] == 1
               and int(r["timestamp"][11:13]) < 6]
    if not tonight:
        return 10.0, 0
    coldest = min(tonight, key=lambda r: r["temp_c"])
    ts      = datetime.strptime(coldest["timestamp"], "%Y-%m-%d %H:%M")
    period  = ts.hour * 2 + ts.minute // 30
    return coldest["temp_c"], period


def analyse_meter(meter_id: int, weather_rows: list[dict]) -> dict:
    consumption = load_consumption(meter_id)
    readings    = _to_readings(consumption)
    baseline    = overnight_baseline_kwh(readings)

    recent_overnight = [kwh for _, p, kwh in readings[-200:] if p in OVERNIGHT_PERIODS]
    if baseline.get("status") == "insufficient_data" or not recent_overnight:
        leak_result = {"alert": False, "max_consecutive_periods": 0,
                       "annualised_waste_kwh": 0, "status": "insufficient_data"}
    else:
        leak_result = detect_gas_leak(recent_overnight, baseline)
        leak_result["status"] = "ok"

    recent_hourly          = _recent_hourly_gas(consumption)
    forecast_low, min_per  = _forecast_overnight_low(weather_rows)
    frost_result           = frost_alert(recent_hourly, forecast_low, min_per)

    today_hdd = daily_hdd(forecast_low)
    last_period_gas = recent_overnight[-1] if recent_overnight else 0.0
    expected_heating = today_hdd > 2.0 and 12 <= datetime.now().hour < 22
    hf_result = heating_failure_frost_alert(
        expected_heating, last_period_gas, forecast_low, forecast_low
    )

    leak_alert_  = leak_result.get("alert", False)
    frost_alert_ = frost_result.get("alert", False) or hf_result.get("alert", False)
    severity     = (frost_result.get("severity") or hf_result.get("severity") or "")

    print(f"  M{meter_id}: "
          f"leak={'ALERT' if leak_alert_ else 'ok'} "
          f"(consec={leak_result.get('max_consecutive_periods', 0)}, "
          f"waste={leak_result.get('annualised_waste_kwh', 0)} kWh/yr)  "
          f"frost={'ALERT ' + severity if frost_alert_ else 'ok'} "
          f"(low={forecast_low:.1f}°C)")

    return {
        "meter_id":               meter_id,
        "leak_alert":             leak_alert_,
        "max_consecutive_periods": leak_result.get("max_consecutive_periods", 0),
        "annualised_waste_kwh":   leak_result.get("annualised_waste_kwh", 0),
        "frost_alert":            frost_alert_,
        "frost_severity":         severity,
        "forecast_low_c":         round(forecast_low, 1),
        "hours_until_minimum":    round(min_per * 0.5, 1),
        "status":                 leak_result.get("status", "ok"),
    }


def main():
    print("Service #10 — Micro-Leak and Frost Detection\n")
    weather_rows = load_weather()
    fields = ["meter_id", "leak_alert", "max_consecutive_periods",
              "annualised_waste_kwh", "frost_alert", "frost_severity",
              "forecast_low_c", "hours_until_minimum", "status"]
    rows = []
    for meter_id in sorted(METERS):
        rows.append(analyse_meter(meter_id, weather_rows))

    with open(OUT_FILE, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows([{f: r.get(f, "") for f in fields} for r in rows])
    print(f"\nWrote {len(rows)} rows to {OUT_FILE}")


if __name__ == "__main__":
    main()

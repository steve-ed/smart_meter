"""
Service #8 — Carbon-Aware Demand Shifting.

Fetches half-hourly carbon intensity for the West Yorkshire DNO region
and recommends when to run each flexible appliance to minimise carbon.

Run: python py/s08_carbon_shifting.py
Outputs: data/s08_carbon_shifting.csv
Requires: data/appliances.csv, internet access to carbonintensity.org.uk
"""

import csv
import json
import urllib.request
from datetime import datetime, timezone

from config import CARBON_REGION_ID, METERS
from tier2_lib import period_to_time

OUT_FILE      = "data/s08_carbon_shifting.csv"
APPLIANCES_IN = "data/appliances.csv"
CARBON_API    = ("https://api.carbonintensity.org.uk/regional/intensity/"
                 "{from_ts}/{to_ts}/regionid/{region_id}")


def fetch_carbon_intensity(region_id: int) -> list[dict]:
    now      = datetime.now(timezone.utc)
    from_ts  = now.strftime("%Y-%m-%dT%H:%MZ")
    to_ts    = datetime.fromtimestamp(
        now.timestamp() + 48 * 3600, tz=timezone.utc
    ).strftime("%Y-%m-%dT%H:%MZ")
    url = CARBON_API.format(from_ts=from_ts, to_ts=to_ts, region_id=region_id)
    with urllib.request.urlopen(url, timeout=15) as resp:
        data = json.loads(resp.read())
    periods = []
    for i, entry in enumerate(data["data"]["data"]):
        periods.append({
            "period_index":   i % 48,
            "intensity_gco2": entry["intensity"]["forecast"],
            "timestamp":      entry["from"],
        })
    return periods


def optimal_shift_window(carbon_periods: list[dict], load: dict) -> dict:
    """
    Find the lowest-carbon contiguous block of min_periods within
    [earliest_period, latest_period].
    """
    window = [cp for cp in carbon_periods
              if load["earliest_period"] <= cp["period_index"] <= load["latest_period"]]

    min_p = load["min_periods"]
    if len(window) < min_p:
        return {"recommendation": None, "reason": "insufficient_window"}

    best_start = 0
    best_carbon = float("inf")
    for i in range(len(window) - min_p + 1):
        block = window[i: i + min_p]
        if block[-1]["period_index"] - block[0]["period_index"] == min_p - 1:
            mean_c = sum(p["intensity_gco2"] for p in block) / min_p
            if mean_c < best_carbon:
                best_carbon = mean_c
                best_start  = i

    best_block = window[best_start: best_start + min_p]

    earliest_block = window[:min_p]
    current_carbon = (sum(p["intensity_gco2"] for p in earliest_block) / len(earliest_block)
                      if earliest_block else best_carbon)

    saving = (current_carbon - best_carbon) * load["typical_kwh"]

    return {
        "appliance":                 load["appliance"],
        "recommended_start_period":  best_block[0]["period_index"],
        "recommended_start_time":    period_to_time(best_block[0]["period_index"]),
        "recommended_end_time":      period_to_time(best_block[-1]["period_index"] + 1),
        "mean_carbon_gco2_per_kwh":  round(best_carbon, 0),
        "current_carbon_gco2_per_kwh": round(current_carbon, 0),
        "carbon_saving_gco2":        round(saving, 0),
        "joint_optimal":             True,
        "recommendation":            period_to_time(best_block[0]["period_index"]),
    }


def load_appliances() -> list[dict]:
    with open(APPLIANCES_IN, newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["meter_id"]        = int(r["meter_id"])
        r["typical_kwh"]     = float(r["typical_kwh"])
        r["min_periods"]     = int(r["min_periods"])
        r["earliest_period"] = int(r["earliest_period"])
        r["latest_period"]   = int(r["latest_period"])
    return rows


def main():
    print("Service #8 — Carbon-Aware Demand Shifting\n")

    try:
        carbon_periods = fetch_carbon_intensity(CARBON_REGION_ID)
        print(f"  Fetched {len(carbon_periods)} carbon intensity periods")
    except Exception as e:
        print(f"  Carbon API unavailable: {e}")
        print("  Writing empty output.")
        fields = ["meter_id", "appliance", "recommended_start_time",
                  "mean_carbon_gco2_per_kwh", "current_carbon_gco2_per_kwh",
                  "carbon_saving_gco2", "joint_optimal"]
        with open(OUT_FILE, "w", newline="") as f:
            csv.DictWriter(f, fieldnames=fields).writeheader()
        return

    appliances = load_appliances()
    rows = []
    for appl in appliances:
        result = optimal_shift_window(carbon_periods, appl)
        if result.get("recommendation") is None:
            print(f"  M{appl['meter_id']} {appl['appliance']}: insufficient window")
            continue
        print(f"  M{appl['meter_id']} {appl['appliance']}: "
              f"best start={result['recommended_start_time']}  "
              f"carbon={result['mean_carbon_gco2_per_kwh']}g/kWh  "
              f"saving={result['carbon_saving_gco2']}g CO2")
        rows.append({
            "meter_id":                 appl["meter_id"],
            "appliance":                appl["appliance"],
            "recommended_start_time":   result["recommended_start_time"],
            "mean_carbon_gco2_per_kwh": result["mean_carbon_gco2_per_kwh"],
            "current_carbon_gco2_per_kwh": result["current_carbon_gco2_per_kwh"],
            "carbon_saving_gco2":       result["carbon_saving_gco2"],
            "joint_optimal":            result["joint_optimal"],
        })

    fields = ["meter_id", "appliance", "recommended_start_time",
              "mean_carbon_gco2_per_kwh", "current_carbon_gco2_per_kwh",
              "carbon_saving_gco2", "joint_optimal"]
    with open(OUT_FILE, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"\nWrote {len(rows)} rows to {OUT_FILE}")


if __name__ == "__main__":
    main()

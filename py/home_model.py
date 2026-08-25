"""
Synthetic indoor temperature model for each of the 5 meters.

Derives HTC and thermal time constant from first-principles building physics
(U-values, Q50 air permeability, y-value thermal bridging, thermal mass).
Simulates half-hourly indoor temperature using:
  - Exact exponential decay when boiler is off
  - Heat balance step when boiler is on (from gas consumption)

Outputs: data/m{n}_indoor_temp.csv  (one file per meter)

See docs/home_model.md for full design rationale.
"""

import csv
import math
import os
from collections import defaultdict

from config import (
    GAS_KWH_PER_M3,
    METERS,
    REGRESSION_END,
    REGRESSION_START,
)

from energy_model import (
    DwellingParams,
    create_dwelling,
    derived_quantities,
)

# ---------------------------------------------------------------------------
# Dwelling parameters — one DwellingParams per meter
# ---------------------------------------------------------------------------

METER_PARAMS: dict[int, DwellingParams] = {
    1: create_dwelling("1970s-semi"),
    2: create_dwelling("1990s-semi"),
    3: create_dwelling("2005-detached"),
    4: create_dwelling("pre-1919-terraced"),
    5: create_dwelling("2015-semi"),
    # Meters 6-15: era-spanning semis, not named archetypes in the spec
    6: DwellingParams(
        label="1975 semi, pre-1976 regs", archetype_id="",
        total_floor_area_m2=88.0, storey_height_m=2.4,
        window_area_m2=14.0, door_area_m2=3.6,
        u_wall=0.60, u_roof=0.35, u_floor=0.70,
        u_window=2.80, u_door=3.00,
        y_value=0.15, q50=10.0, kappa=170,
        sensor_elec_meter=True, sensor_gas_meter=True,
        sensor_outdoor_temp=True, sensor_wind_speed=True,
    ),
    7: DwellingParams(
        label="1980 semi, 1976 regs", archetype_id="",
        total_floor_area_m2=88.0, storey_height_m=2.4,
        window_area_m2=14.0, door_area_m2=3.6,
        u_wall=0.60, u_roof=0.35, u_floor=0.60,
        u_window=2.80, u_door=2.80,
        y_value=0.15, q50=10.0, kappa=165,
        sensor_elec_meter=True, sensor_gas_meter=True,
        sensor_outdoor_temp=True, sensor_wind_speed=True,
    ),
    8: DwellingParams(
        label="1985 semi, 1985 regs", archetype_id="",
        total_floor_area_m2=88.0, storey_height_m=2.4,
        window_area_m2=14.0, door_area_m2=3.6,
        u_wall=0.60, u_roof=0.25, u_floor=0.45,
        u_window=2.80, u_door=2.80,
        y_value=0.12, q50=9.0, kappa=160,
        sensor_elec_meter=True, sensor_gas_meter=True,
        sensor_outdoor_temp=True, sensor_wind_speed=True,
    ),
    9: DwellingParams(
        label="1990 semi, Part L 1990", archetype_id="",
        total_floor_area_m2=88.0, storey_height_m=2.4,
        window_area_m2=15.0, door_area_m2=3.6,
        u_wall=0.45, u_roof=0.25, u_floor=0.45,
        u_window=2.80, u_door=2.80,
        y_value=0.12, q50=9.0, kappa=160,
        sensor_elec_meter=True, sensor_gas_meter=True,
        sensor_outdoor_temp=True, sensor_wind_speed=True,
    ),
    10: DwellingParams(
        label="1995 semi, Part L 1995", archetype_id="",
        total_floor_area_m2=88.0, storey_height_m=2.4,
        window_area_m2=15.0, door_area_m2=3.6,
        u_wall=0.45, u_roof=0.25, u_floor=0.45,
        u_window=2.80, u_door=2.80,
        y_value=0.10, q50=8.0, kappa=158,
        sensor_elec_meter=True, sensor_gas_meter=True,
        sensor_outdoor_temp=True, sensor_wind_speed=True,
    ),
    11: DwellingParams(
        label="2000 semi, Part L 2000", archetype_id="",
        total_floor_area_m2=88.0, storey_height_m=2.4,
        window_area_m2=15.0, door_area_m2=3.6,
        u_wall=0.35, u_roof=0.16, u_floor=0.25,
        u_window=2.00, u_door=2.00,
        y_value=0.09, q50=7.0, kappa=155,
        sensor_elec_meter=True, sensor_gas_meter=True,
        sensor_outdoor_temp=True, sensor_wind_speed=True,
    ),
    12: DwellingParams(
        label="2005 semi, Part L 2002", archetype_id="",
        total_floor_area_m2=88.0, storey_height_m=2.4,
        window_area_m2=15.0, door_area_m2=3.6,
        u_wall=0.35, u_roof=0.16, u_floor=0.25,
        u_window=1.60, u_door=1.60,
        y_value=0.08, q50=6.0, kappa=150,
        sensor_elec_meter=True, sensor_gas_meter=True,
        sensor_outdoor_temp=True, sensor_wind_speed=True,
    ),
    13: DwellingParams(
        label="2010 semi, Part L 2010", archetype_id="",
        total_floor_area_m2=88.0, storey_height_m=2.4,
        window_area_m2=15.0, door_area_m2=3.6,
        u_wall=0.30, u_roof=0.13, u_floor=0.22,
        u_window=1.60, u_door=1.40,
        y_value=0.07, q50=5.0, kappa=148,
        sensor_elec_meter=True, sensor_gas_meter=True,
        sensor_outdoor_temp=True, sensor_wind_speed=True,
    ),
    14: DwellingParams(
        label="2015 semi, Part L 2013", archetype_id="",
        total_floor_area_m2=88.0, storey_height_m=2.4,
        window_area_m2=15.0, door_area_m2=3.6,
        u_wall=0.28, u_roof=0.13, u_floor=0.20,
        u_window=1.40, u_door=1.20,
        y_value=0.05, q50=4.0, kappa=145,
        sensor_elec_meter=True, sensor_gas_meter=True,
        sensor_outdoor_temp=True, sensor_wind_speed=True,
    ),
    15: DwellingParams(
        label="2020 semi, Part L 2021", archetype_id="",
        total_floor_area_m2=88.0, storey_height_m=2.4,
        window_area_m2=15.0, door_area_m2=3.6,
        u_wall=0.18, u_roof=0.11, u_floor=0.13,
        u_window=1.20, u_door=1.00,
        y_value=0.04, q50=3.0, kappa=140,
        sensor_elec_meter=True, sensor_gas_meter=True,
        sensor_outdoor_temp=True, sensor_wind_speed=True,
    ),
}

# Backward-compatible dict-of-dicts for callers that use DWELLING_PARAMS[n]["param"]
# (tier4_analysis.py, app.py). Do not remove.
from dataclasses import asdict as _asdict
DWELLING_PARAMS: dict[int, dict] = {k: _asdict(v) for k, v in METER_PARAMS.items()}

# ---------------------------------------------------------------------------
# Simulation constants
# ---------------------------------------------------------------------------

C_AIR             = 0.33    # Wh/m³K  volumetric heat capacity of air
BOILER_EFFICIENCY = 0.89    # condensing gas boiler
T_SETPOINT        = 20.0    # °C  thermostat setpoint
HEAT_THRESHOLD_KWH = 0.15   # kWh/period — above this = space heating active
SUMMER_MONTHS     = {5, 6, 7, 8, 9}
DT_HOURS          = 0.5     # half-hour step


# ---------------------------------------------------------------------------
# Building physics
# ---------------------------------------------------------------------------

def build_dwelling(p: dict) -> dict:
    """
    Backward-compatible wrapper over derived_quantities().
    Accepts the same dict format as the old DWELLING_PARAMS entries.
    Returns the same keys as the original implementation.
    tier4_analysis.py and app.py use this — do not change the return keys.
    """
    fields = DwellingParams.__dataclass_fields__
    dp = DwellingParams(**{k: v for k, v in p.items() if k in fields})
    d = derived_quantities(dp)
    # Remap to the old key names that callers depend on
    d["c_wh_k"]       = d.pop("c_wh_per_k")
    d["vent_htc"]      = d.pop("ventilation_htc")
    d["envelope_area"] = d.pop("envelope_area_m2")
    d["volume"]        = d.pop("volume_m3")
    d["wall_net"]      = d.pop("wall_net_m2")
    return d


# ---------------------------------------------------------------------------
# Temperature step functions
# ---------------------------------------------------------------------------

def decay_step(t_indoor: float, t_outdoor: float, tau: float) -> float:
    """Exact exponential decay over one half-hour period."""
    return t_outdoor + (t_indoor - t_outdoor) * math.exp(-DT_HOURS / tau)


def heating_step(t_indoor: float, t_outdoor: float,
                 gas_kwh_heating: float,
                 htc: float, c_wh_k: float,
                 efficiency: float = BOILER_EFFICIENCY,
                 t_setpoint: float = T_SETPOINT) -> float:
    """Heat balance over one half-hour period. Capped at t_setpoint."""
    q_boiler = gas_kwh_heating * efficiency * 1000
    q_loss   = htc * (t_indoor - t_outdoor) * DT_HOURS
    delta_t  = (q_boiler - q_loss) / c_wh_k
    return min(t_indoor + delta_t, t_setpoint)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_gas(mpan: str) -> dict[str, float]:
    """
    Returns {timestamp_str: gas_kwh} for the given MPAN.
    Converts m³ to kWh using GAS_KWH_PER_M3.
    Filters to REGRESSION_START..REGRESSION_END.
    """
    gas = {}
    with open("data/consumption_clean.csv", newline="") as f:
        for row in csv.DictReader(f):
            if row["mpxn"] != mpan or row["utility"] != "gas":
                continue
            ts = row["timestamp"]
            if not (REGRESSION_START <= ts[:10] <= REGRESSION_END):
                continue
            try:
                val = float(row["value"])
            except (ValueError, TypeError):
                continue
            gas_kwh = val * GAS_KWH_PER_M3
            # keep higher value on duplicate timestamps (shouldn't happen, but guard)
            if ts not in gas or gas_kwh > gas[ts]:
                gas[ts] = gas_kwh
    return gas


def load_weather() -> dict[str, float]:
    """Returns {timestamp_str: temp_c} from data/weather.csv."""
    weather = {}
    with open("data/weather.csv", newline="") as f:
        for row in csv.DictReader(f):
            ts = row["timestamp"]
            if not (REGRESSION_START <= ts[:10] <= REGRESSION_END):
                continue
            try:
                weather[ts] = float(row["temp_c"])
            except (ValueError, TypeError):
                pass
    return weather


def estimate_base_load(gas: dict[str, float]) -> float:
    """
    Median gas kWh per period in summer months (May–Sep).
    Used to separate hot-water load from space-heating load.
    """
    summer_vals = [
        kwh for ts, kwh in gas.items()
        if int(ts[5:7]) in SUMMER_MONTHS
    ]
    if not summer_vals:
        return 0.08   # fallback: typical hot water kWh/period
    summer_vals.sort()
    return summer_vals[len(summer_vals) // 2]


def build_timeline(gas: dict[str, float],
                   weather: dict[str, float]) -> list[dict]:
    """
    Produce a sorted list of half-hourly period dicts spanning the
    intersection of gas and weather data.
    """
    common = sorted(set(gas) & set(weather))
    periods = []
    for ts in common:
        month = int(ts[5:7])
        hour  = int(ts[11:13])
        minute = int(ts[14:16])
        periods.append({
            "timestamp":    ts,
            "period_index": hour * 2 + minute // 30,
            "month":        month,
            "gas_kwh":      gas[ts],
            "outdoor_c":    weather[ts],
        })
    return periods


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------

def simulate(periods: list[dict],
             htc: float,
             c_wh_k: float,
             tau: float,
             base_load_kwh: float,
             efficiency: float = BOILER_EFFICIENCY,
             t_setpoint: float = T_SETPOINT,
             heat_threshold_kwh: float = HEAT_THRESHOLD_KWH) -> list[dict]:
    results = []
    t_indoor = t_setpoint

    for p in periods:
        t_out    = p["outdoor_c"]
        gas_kwh  = p["gas_kwh"]
        month    = p["month"]

        in_summer = month in SUMMER_MONTHS
        boiler_on = (not in_summer) and (gas_kwh >= heat_threshold_kwh)

        if boiler_on:
            gas_heat = max(gas_kwh - base_load_kwh, 0.0)
            t_indoor = heating_step(t_indoor, t_out, gas_heat, htc, c_wh_k,
                                    efficiency=efficiency,
                                    t_setpoint=t_setpoint)
        else:
            t_indoor = decay_step(t_indoor, t_out, tau)

        t_indoor = max(t_indoor, t_out)

        results.append({
            "timestamp":    p["timestamp"],
            "period_index": p["period_index"],
            "temp_c":       round(t_indoor, 3),
            "boiler_on":    int(boiler_on),
            "outdoor_c":    round(t_out, 2),
        })

    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

FIELDS = ["timestamp", "period_index", "temp_c", "boiler_on", "outdoor_c"]


def main():
    print(f"Loading weather ({REGRESSION_START} to {REGRESSION_END})...")
    weather = load_weather()
    print(f"  {len(weather):,} weather periods loaded\n")

    summary_rows = []

    for meter_num, mpan in METERS.items():
        dp       = METER_PARAMS[meter_num]
        dwelling = derived_quantities(dp)
        dwelling["c_wh_k"]   = dwelling.pop("c_wh_per_k")
        dwelling["vent_htc"] = dwelling.pop("ventilation_htc")

        print(f"Meter {meter_num} — {dp.label}")
        print(f"  MPAN      : {mpan}")
        print(f"  HTC       : {dwelling['htc']:.1f} W/K  "
              f"(fabric {dwelling['fabric_htc']:.1f} + "
              f"bridging {dwelling['bridging_htc']:.1f} + "
              f"vent {dwelling['vent_htc']:.1f})")
        print(f"  ACH       : {dwelling['ach_natural']:.3f} /h")
        print(f"  C         : {dwelling['c_wh_k']:.0f} Wh/K")
        print(f"  tau       : {dwelling['tau_hours']:.1f} h")

        gas = load_gas(mpan)
        if not gas:
            print(f"  WARNING: no gas data found — skipping\n")
            continue

        base_load = estimate_base_load(gas)
        print(f"  Base load : {base_load:.4f} kWh/period (summer median)")

        periods = build_timeline(gas, weather)
        if not periods:
            print(f"  WARNING: no overlapping gas+weather periods — skipping\n")
            continue

        results = simulate(periods, dwelling["htc"], dwelling["c_wh_k"],
                           dwelling["tau_hours"], base_load,
                           efficiency=dp.heating_efficiency,
                           t_setpoint=dp.t_setpoint,
                           heat_threshold_kwh=dp.heat_threshold_kwh)

        out_path = f"data/m{meter_num}_indoor_temp.csv"
        with open(out_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(results)

        boiler_periods = sum(1 for r in results if r["boiler_on"])
        mean_temp = sum(r["temp_c"] for r in results) / len(results)
        min_temp  = min(r["temp_c"] for r in results)

        print(f"  Periods   : {len(results):,}  "
              f"(boiler on: {boiler_periods:,} = "
              f"{boiler_periods/len(results)*100:.1f}%)")
        print(f"  Temp      : mean {mean_temp:.1f}°C  min {min_temp:.1f}°C")
        print(f"  Written   : {out_path}\n")

        summary_rows.append({
            "m":     meter_num,
            "label": dp.label,
            "htc":   dwelling["htc"],
            "tau":   dwelling["tau_hours"],
            "n":     len(results),
            "on%":  boiler_periods / len(results) * 100,
            "mean":  mean_temp,
        })

    # Summary table
    print("-" * 72)
    print(f"{'M':<3} {'Label':<34} {'HTC':>6} {'tau':>6} {'On%':>5} {'Mean':>6}")
    print(f"{'':3} {'':34} {'W/K':>6} {'h':>6} {'':>5} {'°C':>6}")
    print("-" * 72)
    for r in summary_rows:
        print(f"{r['m']:<3} {r['label']:<34} {r['htc']:>6.0f} "
              f"{r['tau']:>6.1f} {r['on%']:>4.1f}% {r['mean']:>6.2f}")
    print("-" * 72)


if __name__ == "__main__":
    main()

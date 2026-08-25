"""
Generate synthetic ground truth for meter 6 (1975 semi, pre-1976 regs).

Runs a full-year simulation for 2024 at 30-minute resolution, applies sensor
noise, and writes both ground truth and sensor observations to a single CSV.

Ground truth columns carry no suffix; sensor observation columns carry _obs.
boiler_on has no noise model so appears once (used by both ground truth and
sensor paths).

Usage (from project root):
    python py/gen_ground_truth_m6.py
"""
import csv
import dataclasses
from datetime import date, timedelta

from energy_model import DwellingParams, derived_quantities
from home_model import METER_PARAMS
from sensor_model import SensorNoiseModel, apply_noise, load_ground_truth
from simulation_runner import DEFAULT_SETPOINT_SCHEDULE, run_simulation
from tier4_analysis import (
    aggregate_tau,
    calculate_hlc,
    find_free_cooling_events,
    fit_tau,
    hlc_to_epc_band,
)

# ---------------------------------------------------------------------------
# Dwelling configuration
# ---------------------------------------------------------------------------

_BASE = METER_PARAMS[6]

DWELLING = DwellingParams(
    **{
        **dataclasses.asdict(_BASE),
        "t_setpoint_schedule":   DEFAULT_SETPOINT_SCHEDULE,
        "boiler_max_kw":         24.0,
        "internal_gains_fraction": 1.0,
    }
)

# ---------------------------------------------------------------------------
# Simulation parameters
# ---------------------------------------------------------------------------

START_DATE   = date(2024, 1, 1)
END_DATE     = date(2024, 12, 31)
SEED         = 42
WEATHER_PATH = "data/weather.csv"
OUTPUT_PATH  = "data/ground_truth_m6_2024.csv"

FIELDS = [
    "timestamp",
    # Ground truth
    "outdoor_temp_c",
    "wind_speed_ms",
    "occupancy",
    "electricity_kwh",
    "gas_kwh",
    "indoor_temp_c",
    "boiler_on",
    # Sensor observations (noisy)
    "outdoor_temp_c_obs",
    "wind_speed_ms_obs",
    "occupancy_obs",
    "electricity_kwh_obs",
    "gas_kwh_obs",
    "indoor_temp_c_obs",
]

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    dates = [START_DATE + timedelta(days=i)
             for i in range((END_DATE - START_DATE).days + 1)]

    print(f"Simulating {len(dates)} days ({dates[0]} to {dates[-1]}) ...")
    print(f"  Dwelling : {DWELLING.label}")
    print(f"  Boiler   : {DWELLING.boiler_max_kw} kW max, "
          f"eff={DWELLING.heating_efficiency}")
    print(f"  Setpoint : scheduled (setback 16°C / comfort 20°C)")
    print(f"  Gains    : {DWELLING.internal_gains_fraction * 100:.0f}% of appliance electricity")

    result = run_simulation(
        DWELLING,
        dates,
        seed=SEED,
        weather_path=WEATHER_PATH,
    )

    # Build ground truth rows
    gt_rows = []
    for ts in result.timestamps:
        gt_rows.append({
            "timestamp":       ts,
            "outdoor_temp_c":  round(result.outdoor_temp_c.get(ts, float("nan")), 2),
            "wind_speed_ms":   round(result.wind_speed_ms.get(ts, float("nan")), 2),
            "occupancy":       bool(result.occupancy[ts]),
            "electricity_kwh": round(result.electricity_kwh[ts], 6),
            "gas_kwh":         round(result.gas_kwh[ts], 6),
            "indoor_temp_c":   result.indoor_temp_c[ts],
            "boiler_on":       bool(result.boiler_on[ts]),
        })

    obs_rows = apply_noise(gt_rows, SensorNoiseModel(), seed=SEED)

    with open(OUTPUT_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for gt, obs in zip(gt_rows, obs_rows):
            writer.writerow({
                "timestamp":           gt["timestamp"],
                "outdoor_temp_c":      gt["outdoor_temp_c"],
                "wind_speed_ms":       gt["wind_speed_ms"],
                "occupancy":           int(gt["occupancy"]),
                "electricity_kwh":     gt["electricity_kwh"],
                "gas_kwh":             gt["gas_kwh"],
                "indoor_temp_c":       gt["indoor_temp_c"],
                "boiler_on":           int(gt["boiler_on"]),
                "outdoor_temp_c_obs":  obs["outdoor_temp_c"],
                "wind_speed_ms_obs":   obs["wind_speed_ms"],
                "occupancy_obs":       int(obs["occupancy"]),
                "electricity_kwh_obs": obs["electricity_kwh"],
                "gas_kwh_obs":         obs["gas_kwh"],
                "indoor_temp_c_obs":   obs["indoor_temp_c"],
            })

    total_elec = sum(result.electricity_kwh.values())
    total_gas  = sum(result.gas_kwh.values())
    slots_written = len(result.timestamps)

    print(f"\nWritten {slots_written:,} rows to {OUTPUT_PATH}")
    print(f"  Annual electricity : {total_elec:,.1f} kWh")
    print(f"  Annual gas         : {total_gas:,.1f} kWh")

    _run_tier4_checks(OUTPUT_PATH, DWELLING)


def _run_tier4_checks(output_path: str, dwelling: DwellingParams) -> None:
    """Run tier 4 EPC estimation using sensor observations and report accuracy."""
    indoor: dict[str, dict] = {}
    with open(output_path, newline="") as f:
        for row in csv.DictReader(f):
            ts = row["timestamp"]
            h, m = int(ts[11:13]), int(ts[14:16])
            indoor[ts] = {
                "temp_c":    float(row["indoor_temp_c_obs"]),
                "boiler_on": int(row["boiler_on"]),
                "outdoor_c": float(row["outdoor_temp_c_obs"]),
                "period":    h * 2 + m // 30,
            }

    dq         = derived_quantities(dwelling)
    true_htc   = dq["htc"]
    true_tau   = dq["tau_hours"]
    floor_area = dwelling.total_floor_area_m2
    true_band  = hlc_to_epc_band(true_htc / floor_area)

    print(f"\n--- Tier 4 validation (sensor observations as input) ---")
    print(f"  True HTC : {true_htc:.1f} W/K    True tau : {true_tau:.1f} h    True band : {true_band['band']}")

    for label, overnight in (("all-hours", False), ("overnight", True)):
        events  = find_free_cooling_events(indoor, overnight_only=overnight)
        fits    = [fit_tau(ev) for ev in events]
        good    = [f for f in fits if f]
        tau_agg = aggregate_tau(good)
        if tau_agg is None:
            print(f"  [{label:<9}]  insufficient events ({len(good)} good fits)")
            continue
        hlc     = calculate_hlc(tau_agg, floor_area, "semi", "1945_1980")
        band    = hlc_to_epc_band(hlc["hlc_per_m2"])
        tau_err = (tau_agg["tau_hours"] - true_tau) / true_tau * 100
        hlc_err = (hlc["hlc_w_per_k"]  - true_htc) / true_htc * 100
        print(f"  [{label:<9}]  events={len(good)}"
              f"  tau={tau_agg['tau_hours']:.1f}h ({tau_err:+.1f}%)"
              f"  HLC={hlc['hlc_w_per_k']:.1f} W/K ({hlc_err:+.1f}%)"
              f"  band={band['band']}  conf={hlc['confidence']}")


if __name__ == "__main__":
    main()

"""
Generate synthetic ground truth for meter 6 (1975 semi, pre-1976 regs).

Runs a full-year simulation for 2024 at 30-minute resolution and writes
the result to data/ground_truth_m6_2024.csv.

Usage (from project root):
    python py/gen_ground_truth_m6.py
"""
import csv
import dataclasses
from datetime import date, timedelta

from energy_model import DwellingParams
from home_model import METER_PARAMS
from simulation_runner import DEFAULT_SETPOINT_SCHEDULE, run_simulation

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

START_DATE  = date(2024, 1, 1)
END_DATE    = date(2024, 12, 31)
SEED        = 42
WEATHER_PATH = "data/weather.csv"
OUTPUT_PATH  = "data/ground_truth_m6_2024.csv"

FIELDS = [
    "timestamp",
    "outdoor_temp_c",
    "wind_speed_ms",
    "occupancy",
    "electricity_kwh",
    "gas_kwh",
    "indoor_temp_c",
    "boiler_on",
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

    with open(OUTPUT_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for ts in result.timestamps:
            writer.writerow({
                "timestamp":      ts,
                "outdoor_temp_c": round(result.outdoor_temp_c.get(ts, float("nan")), 2),
                "wind_speed_ms":  round(result.wind_speed_ms.get(ts, float("nan")), 2),
                "occupancy":      int(result.occupancy[ts]),
                "electricity_kwh": round(result.electricity_kwh[ts], 6),
                "gas_kwh":         round(result.gas_kwh[ts], 6),
                "indoor_temp_c":   result.indoor_temp_c[ts],
                "boiler_on":       int(result.boiler_on[ts]),
            })

    total_elec = sum(result.electricity_kwh.values())
    total_gas  = sum(result.gas_kwh.values())
    slots_written = len(result.timestamps)

    print(f"\nWritten {slots_written:,} rows to {OUTPUT_PATH}")
    print(f"  Annual electricity : {total_elec:,.1f} kWh")
    print(f"  Annual gas         : {total_gas:,.1f} kWh")


if __name__ == "__main__":
    main()

"""
Generate synthetic ground truth and sensor observations for all 15 dwellings.

Runs a full-year 2024 simulation at 30-minute resolution for each meter,
applies SMETS2-grade sensor noise, and writes a CSV per dwelling to data/.

Output files: data/ground_truth_m{1..15}_2024.csv

Usage (from project root):
    python py/gen_ground_truth_all.py
"""
import csv
import dataclasses
from datetime import date, timedelta

from energy_model import DwellingParams, derived_quantities
from home_model import METER_PARAMS
from sensor_model import SensorNoiseModel, apply_noise, smooth_observations
from simulation_runner import DEFAULT_SETPOINT_SCHEDULE, run_simulation
from tier4_analysis import hlc_to_epc_band

START_DATE   = date(2024, 1, 1)
END_DATE     = date(2024, 12, 31)
SEED         = 42
WEATHER_PATH = "data/weather.csv"

FIELDS = [
    "timestamp",
    "outdoor_temp_c", "wind_speed_ms", "occupancy",
    "electricity_kwh", "gas_kwh", "indoor_temp_c", "boiler_on",
    "outdoor_temp_c_obs", "wind_speed_ms_obs", "occupancy_obs",
    "electricity_kwh_obs", "gas_kwh_obs", "indoor_temp_c_obs",
    "indoor_temp_c_z2", "indoor_temp_c_z2_obs", "indoor_temp_c_z2_smooth",
    "outdoor_temp_c_smooth", "indoor_temp_c_smooth",
]

# Boiler sizing: roughly 275 W/m² peak load, rounded to 2 kW, min 14 kW
def _boiler_kw(floor_area: float) -> float:
    return max(14.0, round(floor_area * 0.275 / 2) * 2)


def build_dwelling(meter_num: int) -> DwellingParams:
    base = METER_PARAMS[meter_num]
    z2_area = round(base.total_floor_area_m2 * 0.25)
    return DwellingParams(**{
        **dataclasses.asdict(base),
        "t_setpoint_schedule":            DEFAULT_SETPOINT_SCHEDULE,
        "boiler_max_kw":                  _boiler_kw(base.total_floor_area_m2),
        "internal_gains_fraction":        1.0,
        "zone2_floor_area_m2":            float(z2_area),
        "inter_zone_conductance_w_per_k": 30.0,
        "zone2_t_initial":                18.0,
    })


def simulate_dwelling(meter_num: int, dates: list[date]) -> dict:
    dwelling = build_dwelling(meter_num)
    dq = derived_quantities(dwelling)
    band = hlc_to_epc_band(dq["htc"] / dwelling.total_floor_area_m2)["band"]

    result = run_simulation(dwelling, dates, seed=SEED, weather_path=WEATHER_PATH)

    gt_rows = []
    for ts in result.timestamps:
        gt_rows.append({
            "timestamp":        ts,
            "outdoor_temp_c":   round(result.outdoor_temp_c.get(ts, float("nan")), 2),
            "wind_speed_ms":    round(result.wind_speed_ms.get(ts, float("nan")), 2),
            "occupancy":        bool(result.occupancy[ts]),
            "electricity_kwh":  round(result.electricity_kwh[ts], 6),
            "gas_kwh":          round(result.gas_kwh[ts], 6),
            "indoor_temp_c":    result.indoor_temp_c[ts],
            "boiler_on":        bool(result.boiler_on[ts]),
            "indoor_temp_c_z2": result.indoor_temp_c_z2[ts],
        })

    obs_rows    = apply_noise(gt_rows, SensorNoiseModel(), seed=SEED)
    smooth_rows = smooth_observations(obs_rows)

    output_path = f"data/ground_truth_m{meter_num}_2024.csv"
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for gt, smooth in zip(gt_rows, smooth_rows):
            writer.writerow({
                "timestamp":               gt["timestamp"],
                "outdoor_temp_c":          gt["outdoor_temp_c"],
                "wind_speed_ms":           gt["wind_speed_ms"],
                "occupancy":               int(gt["occupancy"]),
                "electricity_kwh":         gt["electricity_kwh"],
                "gas_kwh":                 gt["gas_kwh"],
                "indoor_temp_c":           gt["indoor_temp_c"],
                "boiler_on":               int(gt["boiler_on"]),
                "outdoor_temp_c_obs":      smooth["outdoor_temp_c"],
                "wind_speed_ms_obs":       smooth["wind_speed_ms"],
                "occupancy_obs":           int(smooth["occupancy"]),
                "electricity_kwh_obs":     smooth["electricity_kwh"],
                "gas_kwh_obs":             smooth["gas_kwh"],
                "indoor_temp_c_obs":       smooth["indoor_temp_c"],
                "indoor_temp_c_z2":        gt["indoor_temp_c_z2"],
                "indoor_temp_c_z2_obs":    smooth["indoor_temp_c_z2"],
                "indoor_temp_c_z2_smooth": smooth["indoor_temp_c_z2_smooth"],
                "outdoor_temp_c_smooth":   smooth["outdoor_temp_c_smooth"],
                "indoor_temp_c_smooth":    smooth["indoor_temp_c_smooth"],
            })

    total_elec = sum(result.electricity_kwh.values())
    total_gas  = sum(result.gas_kwh.values())

    return {
        "meter":      meter_num,
        "label":      dwelling.label,
        "htc":        round(dq["htc"], 1),
        "tau":        round(dq["tau_hours"], 1),
        "band":       band,
        "boiler_kw":  dwelling.boiler_max_kw,
        "z2_m2":      dwelling.zone2_floor_area_m2,
        "elec_kwh":   round(total_elec, 0),
        "gas_kwh":    round(total_gas, 0),
        "path":       output_path,
    }


def main() -> None:
    dates = [START_DATE + timedelta(days=i)
             for i in range((END_DATE - START_DATE).days + 1)]
    print(f"Simulating {len(dates)} days ({dates[0]} to {dates[-1]}) for 15 dwellings ...\n")

    results = []
    for meter_num in sorted(METER_PARAMS):
        print(f"  m{meter_num:>2} {METER_PARAMS[meter_num].label} ...", end=" ", flush=True)
        r = simulate_dwelling(meter_num, dates)
        results.append(r)
        print(f"HTC={r['htc']} W/K  tau={r['tau']}h  band={r['band']}  "
              f"gas={r['gas_kwh']:.0f} kWh  -> {r['path']}")

    w = 100
    print(f"\n{'='*w}")
    print(f"{'M':>2}  {'Label':<38}  {'HTC':>6}  {'tau':>6}  {'Band':>4}  "
          f"{'Elec kWh':>9}  {'Gas kWh':>8}")
    print(f"{'-'*w}")
    for r in results:
        print(f"{r['meter']:>2}  {r['label']:<38}  {r['htc']:>6.1f}  {r['tau']:>6.1f}  "
              f"{r['band']:>4}  {r['elec_kwh']:>9.0f}  {r['gas_kwh']:>8.0f}")
    print(f"{'='*w}")
    print(f"\nWritten {len(results)} CSV files to data/")


if __name__ == "__main__":
    main()

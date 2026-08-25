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
from sensor_model import SensorNoiseModel, apply_noise, load_ground_truth, smooth_observations, smooth_events
from simulation_runner import DEFAULT_SETPOINT_SCHEDULE, run_simulation
from tier4_analysis import (
    aggregate_tau,
    calculate_hlc,
    find_free_cooling_events,
    fit_htc_from_observations,
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
        "t_setpoint_schedule":            DEFAULT_SETPOINT_SCHEDULE,
        "boiler_max_kw":                  24.0,
        "internal_gains_fraction":        1.0,
        "zone2_floor_area_m2":            22.0,   # one bedroom, ~25 % of 88 m²
        "inter_zone_conductance_w_per_k": 30.0,   # ceiling + stairwell coupling
        "zone2_t_initial":                18.0,
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
    # Zone 2 (bedroom) — ground truth, observed, smoothed
    "indoor_temp_c_z2",
    "indoor_temp_c_z2_obs",
    "indoor_temp_c_z2_smooth",
    # Kalman-smoothed zone 1 temperatures
    "outdoor_temp_c_smooth",
    "indoor_temp_c_smooth",
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

    with open(OUTPUT_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for gt, smooth in zip(gt_rows, smooth_rows):
            writer.writerow({
                "timestamp":              gt["timestamp"],
                "outdoor_temp_c":         gt["outdoor_temp_c"],
                "wind_speed_ms":          gt["wind_speed_ms"],
                "occupancy":              int(gt["occupancy"]),
                "electricity_kwh":        gt["electricity_kwh"],
                "gas_kwh":                gt["gas_kwh"],
                "indoor_temp_c":          gt["indoor_temp_c"],
                "boiler_on":              int(gt["boiler_on"]),
                "outdoor_temp_c_obs":     smooth["outdoor_temp_c"],
                "wind_speed_ms_obs":      smooth["wind_speed_ms"],
                "occupancy_obs":          int(smooth["occupancy"]),
                "electricity_kwh_obs":    smooth["electricity_kwh"],
                "gas_kwh_obs":            smooth["gas_kwh"],
                "indoor_temp_c_obs":      smooth["indoor_temp_c"],
                "indoor_temp_c_z2":       gt["indoor_temp_c_z2"],
                "indoor_temp_c_z2_obs":   smooth["indoor_temp_c_z2"],
                "indoor_temp_c_z2_smooth":smooth["indoor_temp_c_z2_smooth"],
                "outdoor_temp_c_smooth":  smooth["outdoor_temp_c_smooth"],
                "indoor_temp_c_smooth":   smooth["indoor_temp_c_smooth"],
            })

    total_elec = sum(result.electricity_kwh.values())
    total_gas  = sum(result.gas_kwh.values())
    slots_written = len(result.timestamps)

    print(f"\nWritten {slots_written:,} rows to {OUTPUT_PATH}")
    print(f"  Annual electricity : {total_elec:,.1f} kWh")
    print(f"  Annual gas         : {total_gas:,.1f} kWh")

    _run_tier4_checks(OUTPUT_PATH, DWELLING, methods=["event_detection", "htc_fit", "htc_fit_2d"])
    _run_window_table(OUTPUT_PATH, DWELLING)


def _run_window_table(output_path: str, dwelling: DwellingParams) -> None:
    """Evaluate htc_fit accuracy across different data windows and tabulate."""
    from datetime import date as _date

    raw_rows: list[dict] = []
    with open(output_path, newline="") as f:
        for row in csv.DictReader(f):
            raw_rows.append(dict(row))

    dq         = derived_quantities(dwelling)
    true_htc   = dq["htc"]
    true_g     = dwelling.inter_zone_conductance_w_per_k
    floor_area = dwelling.total_floor_area_m2
    true_band  = hlc_to_epc_band(true_htc / floor_area)["band"]

    windows = [
        ("Full year",          "2024-01-01", "2024-12-31"),
        ("6 months (Jan–Jun)", "2024-01-01", "2024-06-30"),
        ("1 month  (Jan)",     "2024-01-01", "2024-01-31"),
        ("1 month  (Jul)",     "2024-07-01", "2024-07-31"),
        ("1 week   (Jan)",     "2024-01-08", "2024-01-14"),
        ("1 week   (Jul)",     "2024-07-08", "2024-07-14"),
    ]

    rows_out = []
    for label, start, end in windows:
        subset = [r for r in raw_rows if start <= r["timestamp"][:10] <= end]
        if not subset:
            rows_out.append({"label": label, "n_slots": 0})
            continue

        dates = sorted({_date.fromisoformat(r["timestamp"][:10]) for r in subset})
        obs_rows = [
            {
                "timestamp":        r["timestamp"],
                "indoor_temp_c":    float(r["indoor_temp_c_obs"]),
                "gas_kwh":          float(r["gas_kwh_obs"]),
                "electricity_kwh":  float(r["electricity_kwh_obs"]),
                "indoor_temp_c_z2": (float(r["indoor_temp_c_z2_obs"])
                                     if r.get("indoor_temp_c_z2_obs") else None),
            }
            for r in subset
        ]
        outdoor_temp: dict[str, float] = {}
        wind_speed:   dict[str, float] = {}
        for r in subset:
            ts = r["timestamp"]
            try:
                v = float(r["outdoor_temp_c_obs"])
                if v == v:
                    outdoor_temp[ts] = v
            except (ValueError, TypeError):
                pass
            try:
                v = float(r["wind_speed_ms_obs"])
                if v == v:
                    wind_speed[ts] = v
            except (ValueError, TypeError):
                pass

        fit1d   = fit_htc_from_observations(obs_rows, outdoor_temp, wind_speed, dwelling, dates)
        fit1d_z2 = fit_htc_from_observations(obs_rows, outdoor_temp, wind_speed, dwelling, dates,
                                              use_zone2=True)
        fit2d   = fit_htc_from_observations(obs_rows, outdoor_temp, wind_speed, dwelling, dates,
                                             fit_g=True)
        rows_out.append({
            "label":       label,
            "n_slots":     len(subset),
            "n_heat":      fit1d["n_heating_slots"],
            # 1D zone 1 results
            "err_1d":      (fit1d["htc_w_per_k"] - true_htc) / true_htc * 100,
            "band_1d":     fit1d["band"],
            # 1D zone 2 apparent HTC results
            "htc_z2":      fit1d_z2["htc_w_per_k"],
            "err_z2":      (fit1d_z2["htc_w_per_k"] - true_htc) / true_htc * 100,
            "band_z2":     fit1d_z2["band"],
            # 2D results
            "err_htc_2d":  (fit2d["htc_w_per_k"] - true_htc) / true_htc * 100,
            "g_2d":        fit2d["g_w_per_k"],
            "err_g_2d":    (fit2d["g_w_per_k"] - true_g) / true_g * 100,
            "band_2d":     fit2d["band"],
        })

    w = 108
    print(f"\n--- data window evaluation  "
          f"(true HTC={true_htc:.1f} W/K  G={true_g:.1f} W/K  band {true_band}) ---")
    print("=" * w)
    print(f"{'Window':<22} {'Slots':>6} {'Heat':>5}  "
          f"{'1D (zone 1)':^13}  "
          f"{'1D (zone 2 diag)':^17}  "
          f"{'2D (HTC + G)':^24}")
    print(f"{'':22} {'':6} {'':5}  "
          f"{'HTC err%':>9} {'Bnd':>3}  "
          f"{'app HTC':>7} {'err%':>6} {'Bnd':>3}  "
          f"{'HTC err%':>9} {'G err%':>7} {'Bnd':>3}")
    print("-" * w)
    for r in rows_out:
        if r["n_slots"] == 0:
            print(f"  {r['label']:<20}  no data")
            continue
        b1 = "*" if r["band_1d"] == true_band else " "
        bz = "*" if r["band_z2"] == true_band else " "
        b2 = "*" if r["band_2d"] == true_band else " "
        print(f"{r['label']:<22} {r['n_slots']:>6} {r['n_heat']:>5}  "
              f"{r['err_1d']:>+9.1f}% {r['band_1d']:>3}{b1}  "
              f"{r['htc_z2']:>7.1f} {r['err_z2']:>+6.1f}% {r['band_z2']:>3}{bz}  "
              f"{r['err_htc_2d']:>+9.1f}% {r['err_g_2d']:>+7.1f}% {r['band_2d']:>3}{b2}")
    print("=" * w)
    print(f"  * = correct EPC band ({true_band})")
    print(f"  app HTC = apparent HTC from zone 2 temperature (biased by G={true_g:.0f} W/K)")


def _run_tier4_checks(
    output_path: str,
    dwelling: DwellingParams,
    methods: list[str] | None = None,
) -> None:
    """Run tier 4 EPC estimation using sensor observations and report accuracy.

    methods: which estimation methods to run. Options:
        'event_detection' — free-cooling event fitting (existing approach)
        'htc_fit'         — forward simulation parameter fitting (new approach)
    Defaults to both so results can be compared side-by-side.
    """
    if methods is None:
        methods = ["event_detection", "htc_fit"]

    raw_rows: list[dict] = []
    indoor_z1: dict[str, dict] = {}
    indoor_z2: dict[str, dict] = {}

    with open(output_path, newline="") as f:
        for row in csv.DictReader(f):
            raw_rows.append(dict(row))
            ts = row["timestamp"]
            h, m = int(ts[11:13]), int(ts[14:16])
            period = h * 2 + m // 30
            indoor_z1[ts] = {
                "temp_c":    float(row["indoor_temp_c_obs"]),
                "boiler_on": int(row["boiler_on"]),
                "outdoor_c": float(row["outdoor_temp_c_obs"]),
                "period":    period,
            }
            if "indoor_temp_c_z2_obs" in row and row["indoor_temp_c_z2_obs"]:
                indoor_z2[ts] = {
                    "temp_c":    float(row["indoor_temp_c_z2_obs"]),
                    "boiler_on": int(row["boiler_on"]),
                    "outdoor_c": float(row["outdoor_temp_c_obs"]),
                    "period":    period,
                }

    dq         = derived_quantities(dwelling)
    true_htc   = dq["htc"]
    true_tau   = dq["tau_hours"]
    floor_area = dwelling.total_floor_area_m2
    true_band  = hlc_to_epc_band(true_htc / floor_area)

    print(f"\n--- Tier 4 validation ---")
    print(f"  True HTC : {true_htc:.1f} W/K    True tau : {true_tau:.1f} h    True band : {true_band['band']}")

    if "event_detection" in methods:
        print(f"\n  [Method: free-cooling event detection + per-event Kalman]")
        configs = [
            ("z1 all-hrs", indoor_z1, False),
            ("z1 overngt", indoor_z1, True),
        ]
        if indoor_z2:
            configs.append(("z2 overngt", indoor_z2, True))

        for label, indoor, overnight in configs:
            events  = find_free_cooling_events(indoor, overnight_only=overnight)
            events  = smooth_events(events)
            fits    = [fit_tau(ev) for ev in events]
            good    = [f for f in fits if f]
            tau_agg = aggregate_tau(good)
            if tau_agg is None:
                print(f"  [{label}]  insufficient events ({len(good)} good fits)")
                continue
            hlc     = calculate_hlc(tau_agg, floor_area, "semi", "1945_1980")
            band    = hlc_to_epc_band(hlc["hlc_per_m2"])
            tau_err = (tau_agg["tau_hours"] - true_tau) / true_tau * 100
            hlc_err = (hlc["hlc_w_per_k"]  - true_htc) / true_htc * 100
            print(f"  [{label}]  events={len(good)}"
                  f"  tau={tau_agg['tau_hours']:.1f}h ({tau_err:+.1f}%)"
                  f"  HLC={hlc['hlc_w_per_k']:.1f} W/K ({hlc_err:+.1f}%)"
                  f"  band={band['band']}  conf={hlc['confidence']}")

    if "htc_fit" in methods or "htc_fit_2d" in methods:
        from datetime import date as _date
        dates = sorted({_date.fromisoformat(r["timestamp"][:10]) for r in raw_rows})
        obs_rows = [
            {
                "timestamp":        r["timestamp"],
                "indoor_temp_c":    float(r["indoor_temp_c_obs"]),
                "gas_kwh":          float(r["gas_kwh_obs"]),
                "electricity_kwh":  float(r["electricity_kwh_obs"]),
                "indoor_temp_c_z2": (float(r["indoor_temp_c_z2_obs"])
                                     if r.get("indoor_temp_c_z2_obs") else None),
            }
            for r in raw_rows
        ]
        outdoor_temp: dict[str, float] = {}
        wind_speed:   dict[str, float] = {}
        for r in raw_rows:
            ts = r["timestamp"]
            try:
                v = float(r["outdoor_temp_c_obs"])
                if v == v:
                    outdoor_temp[ts] = v
            except (ValueError, TypeError):
                pass
            try:
                v = float(r["wind_speed_ms_obs"])
                if v == v:
                    wind_speed[ts] = v
            except (ValueError, TypeError):
                pass

    if "htc_fit" in methods:
        print(f"\n  [Method: forward simulation HTC fitting — 1D (zone 1 temp + gas)]")
        print(f"  Fitting over {len(dates)} days, {len(obs_rows)} slots ...")
        result = fit_htc_from_observations(
            obs_rows, outdoor_temp, wind_speed, dwelling, dates
        )
        htc_err = (result["htc_w_per_k"] - true_htc) / true_htc * 100
        print(f"  [htc_fit]  HTC={result['htc_w_per_k']:.1f} W/K ({htc_err:+.1f}%)"
              f"  scale={result['htc_scale']:.3f}"
              f"  band={result['band']}"
              f"  RMSE_T={result['rmse_temp_c']:.3f}°C"
              f"  RMSE_G={result['rmse_gas_kwh']:.4f} kWh"
              f"  n_heating={result['n_heating_slots']}")

    if "htc_fit_2d" in methods:
        true_g = dwelling.inter_zone_conductance_w_per_k
        print(f"\n  [Method: forward simulation HTC+G fitting — 2D (zone 1 + zone 2 temp + gas)]")
        print(f"  Fitting over {len(dates)} days, {len(obs_rows)} slots ...")
        result2 = fit_htc_from_observations(
            obs_rows, outdoor_temp, wind_speed, dwelling, dates, fit_g=True
        )
        htc_err = (result2["htc_w_per_k"] - true_htc) / true_htc * 100
        g_err   = (result2["g_w_per_k"]   - true_g)   / true_g   * 100
        print(f"  [htc_fit_2d]  HTC={result2['htc_w_per_k']:.1f} W/K ({htc_err:+.1f}%)"
              f"  G={result2['g_w_per_k']:.1f} W/K ({g_err:+.1f}%)"
              f"  band={result2['band']}"
              f"  RMSE_T1={result2['rmse_temp_c']:.3f}°C"
              f"  RMSE_T2={result2['rmse_temp_c_z2']:.3f}°C"
              f"  RMSE_G={result2['rmse_gas_kwh']:.4f} kWh")


if __name__ == "__main__":
    main()

"""
Tier 4 — EPC measurement from indoor temperature decay.

Services implemented:
  #13  Free-cooling event detection and tau / HLC fitting
  #13a Measured vs modelled (SAP) performance gap
  #13b Monthly rolling dynamic EPC band
  #14  Comfort vs cost weekly report

Inputs:
  data/m{n}_indoor_temp.csv   (from home_model.py)
  data/consumption.csv
  data/weather.csv
  data/tariff.csv             (m1 only; others use config flat rates)

Outputs:
  data/m{n}_tier4_events.csv      per-event decay fits
  data/m{n}_tier4_rolling_epc.csv monthly EPC band series
  data/tier4_summary.csv          cross-meter summary table
  Console: per-meter report + summary table
"""

import csv
import math
import os
from collections import defaultdict
from datetime import date, timedelta

from config import (
    ELEC_RATE_P_KWH,
    GAS_KWH_PER_M3,
    GAS_RATE_P_KWH,
    METERS,
    REGRESSION_END,
    REGRESSION_START,
    WINTER_END,
    WINTER_START,
)
from home_model import DWELLING_PARAMS, build_dwelling

# ---------------------------------------------------------------------------
# Meter metadata (property type / build era for HLC lookup)
# ---------------------------------------------------------------------------

METER_META = {
    1: {"property_type": "semi",     "build_era": "1945_1980"},
    2: {"property_type": "semi",     "build_era": "post_1980"},
    3: {"property_type": "detached", "build_era": "post_1980"},
    4: {"property_type": "terraced", "build_era": "pre_1945"},
    5: {"property_type": "semi",     "build_era": "post_1980"},
}

# ---------------------------------------------------------------------------
# Building physics constants (from tier4_indoor_temperature.md)
# ---------------------------------------------------------------------------

CAPACITANCE_WH_PER_K_PER_M2 = {
    ("detached",  "pre_1945"):  240,
    ("detached",  "1945_1980"): 190,
    ("detached",  "post_1980"): 155,
    ("semi",      "pre_1945"):  220,
    ("semi",      "1945_1980"): 175,
    ("semi",      "post_1980"): 145,
    ("terraced",  "pre_1945"):  210,
    ("terraced",  "1945_1980"): 165,
    ("terraced",  "post_1980"): 135,
    ("flat",      "pre_1945"):  170,
    ("flat",      "1945_1980"): 140,
    ("flat",      "post_1980"): 115,
}

EPC_BANDS = [
    ("A", 0.00, 0.70),
    ("B", 0.70, 0.95),
    ("C", 0.95, 1.30),
    ("D", 1.30, 1.75),
    ("E", 1.75, 2.35),
    ("F", 2.35, 3.20),
    ("G", 3.20, 99.9),
]

# Free-cooling event detection thresholds
MIN_DELTA_T_C        = 3.0    # indoor must exceed outdoor by at least this
MIN_DECAY_PERIODS    = 4      # minimum event length (2 hours)
MAX_OUTDOOR_VARY_C   = 2.0    # discard events with unstable outdoor temperature
R2_THRESHOLD         = 0.85   # minimum R² to accept a tau fit
DT_HOURS             = 0.5

# Overnight window: 23:00–05:30 (periods 46, 47, 0–11)
# Excludes solar gain, cooking, occupancy metabolic heat
OVERNIGHT_PERIODS = set(range(0, 12)) | {46, 47}

# Comfort thresholds (WHO / CIBSE)
COMFORT_LOWER_C = 18.0
HEALTH_RISK_C   = 16.0
OCCUPIED_PERIODS = set(range(14, 45))   # 07:00–22:30


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

def load_indoor(meter_num: int) -> dict[str, dict]:
    """Returns {timestamp: {temp_c, boiler_on, outdoor_c}}."""
    path = f"data/m{meter_num}_indoor_temp.csv"
    result = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            result[row["timestamp"]] = {
                "temp_c":    float(row["temp_c"]),
                "boiler_on": int(row["boiler_on"]),
                "outdoor_c": float(row["outdoor_c"]),
                "period":    int(row["period_index"]),
            }
    return result


GAS_MAX_M3_PER_PERIOD  = 5.0    # 112 kW boiler — above this is a sentinel/error
ELEC_MAX_KWH_PER_PERIOD = 50.0  # 100 kW load — above this is a sentinel/error


def load_consumption(mpan: str, utility: str,
                     start: str, end: str) -> dict[str, float]:
    """Returns {timestamp: value} filtered to date window."""
    result = {}
    with open("data/consumption.csv", newline="") as f:
        for row in csv.DictReader(f):
            if row["mpxn"] != mpan or row["utility"] != utility:
                continue
            ts = row["timestamp"]
            if not (start <= ts[:10] <= end):
                continue
            try:
                val = float(row["value"])
            except (ValueError, TypeError):
                continue
            # Reject meter sentinel / rollover values
            if utility == "gas" and val >= GAS_MAX_M3_PER_PERIOD:
                continue
            if utility == "electricity" and val >= ELEC_MAX_KWH_PER_PERIOD:
                continue
            if utility == "gas":
                val = val * GAS_KWH_PER_M3
            result[ts] = val
    return result


def load_tariff(mpan: str) -> dict[int, float]:
    """Returns {period_index: rate_p_per_kwh} for electricity."""
    rates = {}
    with open("data/tariff.csv", newline="") as f:
        for row in csv.DictReader(f):
            if row["mpan"] != mpan or row["energy_type"] != "electricity":
                continue
            if row["type"] != "unit_rate":
                continue
            try:
                ts  = row["timestamp"]
                p   = int(ts[11:13]) * 2 + int(ts[14:16]) // 30
                rates[p] = float(row["value"])
            except (ValueError, IndexError):
                continue
    return rates


# ---------------------------------------------------------------------------
# Service #13 — free cooling event detection
# ---------------------------------------------------------------------------

def find_free_cooling_events(indoor: dict[str, dict],
                             overnight_only: bool = False) -> list[list[dict]]:
    """Detect contiguous boiler-off periods with falling indoor temperature.

    overnight_only: restrict to periods 23:00–05:30 to reduce solar gain,
    occupancy and cooking disturbances.
    """
    timestamps = sorted(indoor)
    events, current = [], []

    for ts in timestamps:
        p = indoor[ts]

        if overnight_only and p["period"] not in OVERNIGHT_PERIODS:
            if len(current) >= MIN_DECAY_PERIODS:
                events.append(current)
            current = []
            continue

        boiler_off  = p["boiler_on"] == 0
        warm_enough = (p["temp_c"] - p["outdoor_c"]) >= MIN_DELTA_T_C

        falling = True
        if current:
            prev = current[-1]
            falling = (p["temp_c"] - prev["temp_c"]) <= 0.3  # allow tiny rise

        if boiler_off and warm_enough and falling:
            current.append({"timestamp": ts, **p})
        else:
            if len(current) >= MIN_DECAY_PERIODS:
                events.append(current)
            current = []

    if len(current) >= MIN_DECAY_PERIODS:
        events.append(current)

    # discard events with unstable outdoor temperature
    stable = []
    for ev in events:
        out_temps = [p["outdoor_c"] for p in ev]
        if max(out_temps) - min(out_temps) <= MAX_OUTDOOR_VARY_C:
            stable.append(ev)

    return stable


# ---------------------------------------------------------------------------
# Service #13 — tau fitting
# ---------------------------------------------------------------------------

def fit_tau(event: list[dict]) -> dict | None:
    """Fit exponential decay to a single free-cooling event. Returns None if poor fit."""
    outdoor_mean = sum(p["outdoor_c"] for p in event) / len(event)
    delta_T = [p["temp_c"] - outdoor_mean for p in event]

    # Require mostly monotone decrease (allow 1 non-monotone step)
    non_mono = sum(1 for i in range(1, len(delta_T)) if delta_T[i] >= delta_T[i - 1])
    if non_mono > 1:
        return None

    xs, ys = [], []
    for i, dT in enumerate(delta_T):
        if dT > 1.0:
            xs.append(i * DT_HOURS)
            ys.append(math.log(dT))

    if len(xs) < 4:
        return None

    n   = len(xs)
    sx  = sum(xs);     sy  = sum(ys)
    sxx = sum(x*x for x in xs)
    sxy = sum(x*y for x, y in zip(xs, ys))
    den = n * sxx - sx * sx

    if abs(den) < 1e-12:
        return None

    b = (n * sxy - sx * sy) / den   # slope = -1/tau
    a = (sy - b * sx) / n

    if b >= 0:
        return None

    tau = -1.0 / b

    y_mean = sy / n
    ss_tot = sum((y - y_mean) ** 2 for y in ys)
    ss_res = sum((y - (a + b * x)) ** 2 for x, y in zip(xs, ys))
    r2     = 1.0 - ss_res / ss_tot if ss_tot > 1e-12 else 0.0

    if r2 < R2_THRESHOLD:
        return None

    return {
        "timestamp":     event[0]["timestamp"],
        "tau_hours":     round(tau, 3),
        "r_squared":     round(r2, 6),
        "n_points":      n,
        "delta_T_start": round(delta_T[0], 3),
        "outdoor_mean":  round(outdoor_mean, 2),
        "duration_h":    round(len(event) * DT_HOURS, 1),
        "quality":       "good" if r2 >= 0.95 else "acceptable",
    }


def aggregate_tau(fits: list[dict]) -> dict | None:
    """Weighted aggregate tau across events. Weight = R² × n_points."""
    good = [f for f in fits if f is not None]
    if len(good) < 5:
        return None

    weights = [f["r_squared"] * f["n_points"] for f in good]
    total_w = sum(weights)
    tau_w   = sum(f["tau_hours"] * w for f, w in zip(good, weights)) / total_w

    var_w = sum(w * (f["tau_hours"] - tau_w) ** 2
                for f, w in zip(good, weights)) / total_w
    std_w = var_w ** 0.5

    return {
        "tau_hours":     round(tau_w, 3),
        "tau_std":       round(std_w, 3),
        "tau_95ci_low":  round(tau_w - 1.96 * std_w, 3),
        "tau_95ci_high": round(tau_w + 1.96 * std_w, 3),
        "n_events":      len(good),
        "n_good":        sum(1 for f in good if f["quality"] == "good"),
    }


# ---------------------------------------------------------------------------
# Service #13 — HLC calculation
# ---------------------------------------------------------------------------

def calculate_hlc(tau: dict, floor_area: float,
                  property_type: str, build_era: str) -> dict:
    key       = (property_type, build_era)
    c_per_m2  = CAPACITANCE_WH_PER_K_PER_M2.get(key, 170)
    C         = c_per_m2 * floor_area

    hlc      = C / tau["tau_hours"]
    hlc_low  = C / tau["tau_95ci_high"]
    hlc_high = C / tau["tau_95ci_low"]

    return {
        "hlc_w_per_k":    round(hlc, 1),
        "hlc_95ci_low":   round(hlc_low, 1),
        "hlc_95ci_high":  round(hlc_high, 1),
        "hlc_per_m2":     round(hlc / floor_area, 3),
        "capacitance_wh_per_k": round(C, 0),
    }


def hlc_to_epc_band(hlc_per_m2: float) -> dict:
    for band, lo, hi in EPC_BANDS:
        if lo <= hlc_per_m2 < hi:
            pos = (hlc_per_m2 - lo) / (hi - lo)
            return {"band": band, "position": round(pos, 3)}
    return {"band": "G", "position": 1.0}


# ---------------------------------------------------------------------------
# Service #13a — performance gap
# ---------------------------------------------------------------------------

def performance_gap(hlc_result: dict, true_htc: float) -> dict:
    hlc     = hlc_result["hlc_w_per_k"]
    gap     = hlc - true_htc
    gap_pct = gap / true_htc * 100

    if gap_pct < -10:
        interp = "performs_better_than_reference"
    elif gap_pct < 10:
        interp = "consistent_with_reference"
    elif gap_pct < 30:
        interp = "moderate_gap"
    elif gap_pct < 60:
        interp = "significant_gap"
    else:
        interp = "severe_gap"

    return {
        "measured_hlc":  hlc,
        "reference_htc": round(true_htc, 1),
        "gap_w_per_k":   round(gap, 1),
        "gap_pct":       round(gap_pct, 1),
        "interpretation": interp,
    }


# ---------------------------------------------------------------------------
# Service #13b — rolling monthly EPC
# ---------------------------------------------------------------------------

def rolling_epc(indoor: dict[str, dict], dwelling: dict,
                floor_area: float, property_type: str,
                build_era: str,
                overnight_only: bool = False) -> list[dict]:
    """
    Compute tau and EPC band for each calendar month using events
    within an 8-week rolling window ending at month end.
    """
    # Group events by month
    events = find_free_cooling_events(indoor, overnight_only=overnight_only)
    fits_by_month: dict[str, list] = defaultdict(list)

    for ev in events:
        month_key = ev[0]["timestamp"][:7]
        fit = fit_tau(ev)
        if fit:
            fits_by_month[month_key].append(fit)

    # Sort months present in data
    all_months = sorted({ts[:7] for ts in indoor})
    results = []

    for i, month in enumerate(all_months):
        # 8-week rolling window: this month + 3 prior months
        window_months = all_months[max(0, i - 3): i + 1]
        window_fits   = []
        for m in window_months:
            window_fits.extend(fits_by_month.get(m, []))

        tau_agg = aggregate_tau(window_fits)
        if tau_agg is None:
            results.append({"month": month, "band": None,
                            "tau_hours": None, "hlc_w_per_k": None,
                            "n_events": len(window_fits),
                            "status": "insufficient_events"})
            continue

        hlc    = calculate_hlc(tau_agg, floor_area, property_type, build_era)
        band   = hlc_to_epc_band(hlc["hlc_per_m2"])
        results.append({
            "month":      month,
            "band":       band["band"],
            "tau_hours":  tau_agg["tau_hours"],
            "hlc_w_per_k": hlc["hlc_w_per_k"],
            "n_events":   tau_agg["n_events"],
            "status":     "ok",
        })

    return results


# ---------------------------------------------------------------------------
# Service #14 — comfort vs cost
# ---------------------------------------------------------------------------

def comfort_score(temp_c: float) -> float:
    if temp_c < HEALTH_RISK_C:
        return 0.0
    if temp_c < COMFORT_LOWER_C:
        return (temp_c - HEALTH_RISK_C) / (COMFORT_LOWER_C - HEALTH_RISK_C)
    return 1.0


def comfort_cost_report(indoor: dict[str, dict],
                        elec: dict[str, float],
                        gas: dict[str, float],
                        tariff_rates: dict[int, float],
                        default_elec_rate: float,
                        gas_rate: float,
                        start: str,
                        end: str) -> dict:
    """Weekly comfort and cost summary over the analysis window."""
    comfort_occ, comfort_vac_cost_p = [], 0.0
    occ_cost_p = total_cost_p = 0.0
    cold_periods = health_risk_periods = 0

    for ts in sorted(indoor):
        if not (start <= ts[:10] <= end):
            continue
        p     = indoor[ts]
        period = p["period"]
        occupied = period in OCCUPIED_PERIODS
        t_in  = p["temp_c"]

        elec_kwh  = elec.get(ts, 0.0)
        gas_kwh   = gas.get(ts, 0.0)
        elec_rate = tariff_rates.get(period, default_elec_rate)

        period_cost_p = elec_kwh * elec_rate + gas_kwh * gas_rate
        total_cost_p += period_cost_p

        if occupied:
            occ_cost_p += period_cost_p
            comfort_occ.append(comfort_score(t_in))
            if t_in < COMFORT_LOWER_C:
                cold_periods += 1
            if t_in < HEALTH_RISK_C:
                health_risk_periods += 1
        else:
            comfort_vac_cost_p += period_cost_p

    n_occ = len(comfort_occ)
    mean_comfort  = sum(comfort_occ) / n_occ if n_occ else None
    pct_in_zone   = sum(1 for s in comfort_occ if s >= 1.0) / n_occ * 100 if n_occ else None
    vacant_pct    = comfort_vac_cost_p / total_cost_p * 100 if total_cost_p else 0.0

    return {
        "total_cost_gbp":        round(total_cost_p / 100, 2),
        "occupied_cost_gbp":     round(occ_cost_p / 100, 2),
        "vacant_cost_gbp":       round(comfort_vac_cost_p / 100, 2),
        "vacant_cost_pct":       round(vacant_pct, 1),
        "mean_comfort_score":    round(mean_comfort, 3) if mean_comfort is not None else None,
        "pct_in_comfort_zone":   round(pct_in_zone, 1) if pct_in_zone is not None else None,
        "cold_occupied_periods": cold_periods,
        "health_risk_periods":   health_risk_periods,
    }


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def write_events_csv(meter_num: int, fits: list[dict]):
    path = f"data/m{meter_num}_tier4_events.csv"
    fields = ["timestamp", "tau_hours", "r_squared", "n_points",
              "delta_T_start", "outdoor_mean", "duration_h", "quality"]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows([fit for fit in fits if fit])


def write_rolling_epc_csv(meter_num: int, series: list[dict]):
    path = f"data/m{meter_num}_tier4_rolling_epc.csv"
    fields = ["month", "band", "tau_hours", "hlc_w_per_k", "n_events", "status"]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(series)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def analyse_meter(meter_num: int, mpan: str, indoor: dict,
                  gas: dict, elec: dict, tariff: dict,
                  overnight_only: bool) -> dict | None:
    """Run #13/#13a/#13b for one meter under one event-filter mode."""
    params     = DWELLING_PARAMS[meter_num]
    meta       = METER_META[meter_num]
    dwelling   = build_dwelling(params)
    floor_area = params["total_floor_area_m2"]
    true_htc   = dwelling["htc"]
    true_tau   = dwelling["tau_hours"]
    true_band  = hlc_to_epc_band(true_htc / floor_area)

    events = find_free_cooling_events(indoor, overnight_only=overnight_only)
    fits   = [fit_tau(ev) for ev in events]
    good   = [f for f in fits if f]

    tau_agg = aggregate_tau(good)
    if tau_agg is None:
        return None

    hlc_result  = calculate_hlc(tau_agg, floor_area,
                                meta["property_type"], meta["build_era"])
    band_result = hlc_to_epc_band(hlc_result["hlc_per_m2"])
    gap         = performance_gap(hlc_result, true_htc)

    return {
        "m":          meter_num,
        "label":      params["label"],
        "true_htc":   true_htc,
        "true_tau":   true_tau,
        "fit_tau":    tau_agg["tau_hours"],
        "tau_lo":     tau_agg["tau_95ci_low"],
        "tau_hi":     tau_agg["tau_95ci_high"],
        "fit_htc":    hlc_result["hlc_w_per_k"],
        "gap_pct":    gap["gap_pct"],
        "interp":     gap["interpretation"],
        "epc_true":   true_band["band"],
        "epc_fitted": band_result["band"],
        "n_events":   len(good),
    }


def print_summary_table(rows: list[dict], title: str):
    w = 92
    print(f"\n\n{'='*w}")
    print(title)
    print(f"{'='*w}")
    hdr = (f"{'M':<3} {'Label':<30} {'tau true':>8} {'tau fit':>7} "
           f"{'tau err%':>8} {'HTC true':>8} {'HLC fit':>7} "
           f"{'Gap%':>6} {'Band':>5} {'Events':>7}")
    print(hdr)
    print("-" * w)
    for r in rows:
        if r is None:
            continue
        err = (r["fit_tau"] - r["true_tau"]) / r["true_tau"] * 100
        print(f"{r['m']:<3} {r['label']:<30} "
              f"{r['true_tau']:>8.1f} {r['fit_tau']:>7.1f} "
              f"{err:>+8.1f}% {r['true_htc']:>8.1f} {r['fit_htc']:>7.1f} "
              f"{r['gap_pct']:>+6.1f}% {r['epc_fitted']:>5}  "
              f"{r['n_events']:>7}")
    print("=" * w)


def main():
    all_indoor, all_gas, all_elec, all_tariff = {}, {}, {}, {}

    # Pre-load all data once
    for meter_num, mpan in METERS.items():
        all_indoor[meter_num] = load_indoor(meter_num)
        all_gas[meter_num]    = load_consumption(mpan, "gas",
                                                 REGRESSION_START, REGRESSION_END)
        all_elec[meter_num]   = load_consumption(mpan, "electricity",
                                                 WINTER_START, WINTER_END)
        all_tariff[meter_num] = load_tariff(mpan)

    summary_all, summary_night = [], []

    for meter_num, mpan in METERS.items():
        params   = DWELLING_PARAMS[meter_num]
        dwelling = build_dwelling(params)
        meta     = METER_META[meter_num]
        floor_area = params["total_floor_area_m2"]

        indoor = all_indoor[meter_num]
        gas    = all_gas[meter_num]
        elec   = all_elec[meter_num]
        tariff = all_tariff[meter_num]

        print(f"\n{'='*60}")
        print(f"Meter {meter_num} — {params['label']}")
        print(f"{'='*60}")
        print(f"  True HTC : {dwelling['htc']:.1f} W/K    True tau : {dwelling['tau_hours']:.1f} h")
        print(f"  Indoor   : {len(indoor):,} periods    Gas : {len(gas):,} periods")

        # --- All-hours pass ---
        r_all = analyse_meter(meter_num, mpan, indoor, gas, elec, tariff,
                              overnight_only=False)
        if r_all:
            summary_all.append(r_all)
            err = (r_all["fit_tau"] - r_all["true_tau"]) / r_all["true_tau"] * 100
            print(f"\n  [ALL hours]  events={r_all['n_events']}  "
                  f"tau={r_all['fit_tau']:.1f}h ({err:+.1f}%)  "
                  f"HLC={r_all['fit_htc']:.1f} W/K  band={r_all['epc_fitted']}  "
                  f"gap={r_all['gap_pct']:+.1f}%")
        else:
            summary_all.append(None)
            print("  [ALL hours]  insufficient events")

        # Write events CSV from all-hours pass
        events_all = find_free_cooling_events(indoor, overnight_only=False)
        write_events_csv(meter_num, [fit_tau(ev) for ev in events_all])

        # --- Overnight-only pass ---
        r_night = analyse_meter(meter_num, mpan, indoor, gas, elec, tariff,
                                overnight_only=True)
        if r_night:
            summary_night.append(r_night)
            err = (r_night["fit_tau"] - r_night["true_tau"]) / r_night["true_tau"] * 100
            print(f"  [OVERNIGHT]  events={r_night['n_events']}  "
                  f"tau={r_night['fit_tau']:.1f}h ({err:+.1f}%)  "
                  f"HLC={r_night['fit_htc']:.1f} W/K  band={r_night['epc_fitted']}  "
                  f"gap={r_night['gap_pct']:+.1f}%")
        else:
            summary_night.append(None)
            print("  [OVERNIGHT]  insufficient events")

        # --- Service #13b rolling EPC (overnight) ---
        epc_series = rolling_epc(indoor, dwelling, floor_area,
                                 meta["property_type"], meta["build_era"],
                                 overnight_only=True)
        write_rolling_epc_csv(meter_num, epc_series)
        valid = [s for s in epc_series if s["band"]]
        if valid:
            bands = [s["band"] for s in valid]
            bc = {b: bands.count(b) for b in sorted(set(bands))}
            print(f"  [#13b OVN]   rolling EPC: {len(valid)} months  bands: {bc}")

        # --- Service #14 comfort vs cost (unchanged — not affected by event filter) ---
        comfort = comfort_cost_report(
            indoor, elec, gas, tariff, ELEC_RATE_P_KWH, GAS_RATE_P_KWH,
            WINTER_START, WINTER_END
        )
        print(f"\n  [#14] Total cost GBP {comfort['total_cost_gbp']:.2f}  "
              f"vacant {comfort['vacant_cost_pct']:.1f}%  "
              f"comfort {comfort['pct_in_comfort_zone']:.1f}%  "
              f"health risk {comfort['health_risk_periods']} periods")

    # --- Summary tables ---
    print_summary_table(summary_all,
        f"ALL-HOURS EVENTS  (regression {REGRESSION_START} to {REGRESSION_END})")
    print_summary_table(summary_night,
        f"OVERNIGHT-ONLY EVENTS 23:00-05:30  (regression {REGRESSION_START} to {REGRESSION_END})")

    # --- Comparison table ---
    w = 80
    print(f"\n\n{'='*w}")
    print("COMPARISON: all-hours vs overnight-only")
    print(f"{'='*w}")
    hdr = (f"{'M':<3} {'Label':<30} {'tau all':>7} {'tau ovn':>7} "
           f"{'err all':>7} {'err ovn':>7} {'band all':>8} {'band ovn':>8}")
    print(hdr)
    print("-" * w)
    for ra, rn in zip(summary_all, summary_night):
        if ra is None or rn is None:
            continue
        err_a = (ra["fit_tau"] - ra["true_tau"]) / ra["true_tau"] * 100
        err_n = (rn["fit_tau"] - rn["true_tau"]) / rn["true_tau"] * 100
        print(f"{ra['m']:<3} {ra['label']:<30} "
              f"{ra['fit_tau']:>7.1f} {rn['fit_tau']:>7.1f} "
              f"{err_a:>+7.1f}% {err_n:>+7.1f}% "
              f"{ra['epc_fitted']:>8} {rn['epc_fitted']:>8}")
    print("=" * w)

    # Write summary CSVs
    fields = ["m", "label", "true_htc", "true_tau", "fit_tau", "fit_htc",
              "gap_pct", "epc_true", "epc_fitted", "n_events"]
    for tag, rows in [("all", summary_all), ("overnight", summary_night)]:
        path = f"data/tier4_summary_{tag}.csv"
        with open(path, "w", newline="") as f:
            w2 = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            w2.writeheader()
            w2.writerows(r for r in rows if r)
    print(f"\nWritten: data/tier4_summary_all.csv")
    print(f"         data/tier4_summary_overnight.csv")
    for n in METERS:
        print(f"         data/m{n}_tier4_events.csv")
        print(f"         data/m{n}_tier4_rolling_epc.csv")


if __name__ == "__main__":
    main()

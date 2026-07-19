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

def find_free_cooling_events(indoor: dict[str, dict]) -> list[list[dict]]:
    """Detect contiguous boiler-off periods with falling indoor temperature."""
    timestamps = sorted(indoor)
    events, current = [], []

    for ts in timestamps:
        p = indoor[ts]
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
                build_era: str) -> list[dict]:
    """
    Compute tau and EPC band for each calendar month using events
    within an 8-week rolling window ending at month end.
    """
    # Group events by month
    events = find_free_cooling_events(indoor)
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

def main():
    summary = []

    for meter_num, mpan in METERS.items():
        params   = DWELLING_PARAMS[meter_num]
        meta     = METER_META[meter_num]
        dwelling = build_dwelling(params)
        floor_area = params["total_floor_area_m2"]
        true_htc   = dwelling["htc"]
        true_tau   = dwelling["tau_hours"]

        print(f"\n{'='*60}")
        print(f"Meter {meter_num} — {params['label']}")
        print(f"{'='*60}")
        print(f"  True HTC : {true_htc:.1f} W/K    True tau : {true_tau:.1f} h")

        # Load data
        indoor = load_indoor(meter_num)
        gas    = load_consumption(mpan, "gas",         REGRESSION_START, REGRESSION_END)
        elec   = load_consumption(mpan, "electricity", WINTER_START,     WINTER_END)
        tariff = load_tariff(mpan)
        default_elec = ELEC_RATE_P_KWH

        print(f"  Indoor   : {len(indoor):,} periods")
        print(f"  Gas      : {len(gas):,} periods")

        # --- Service #13: detect events and fit tau ---
        events = find_free_cooling_events(indoor)
        fits   = [fit_tau(ev) for ev in events]
        good   = [f for f in fits if f]
        write_events_csv(meter_num, fits)

        print(f"\n  [#13] Free cooling events: {len(events)}  "
              f"good fits: {len(good)}")

        tau_agg = aggregate_tau(good)
        if tau_agg is None:
            print("  WARNING: insufficient good fits for tau aggregate")
            summary.append({"m": meter_num, "status": "insufficient_data"})
            continue

        print(f"  [#13] tau fitted  : {tau_agg['tau_hours']:.1f} h "
              f"(95% CI {tau_agg['tau_95ci_low']:.1f}–{tau_agg['tau_95ci_high']:.1f})")
        print(f"  [#13] tau true    : {true_tau:.1f} h  "
              f"error: {(tau_agg['tau_hours'] - true_tau)/true_tau*100:+.1f}%")

        # --- HLC ---
        hlc_result = calculate_hlc(tau_agg, floor_area,
                                   meta["property_type"], meta["build_era"])
        band_result = hlc_to_epc_band(hlc_result["hlc_per_m2"])
        print(f"  [#13] HLC fitted  : {hlc_result['hlc_w_per_k']:.1f} W/K  "
              f"({hlc_result['hlc_per_m2']:.3f} W/K/m2)  -> EPC band {band_result['band']}")

        # --- Service #13a: performance gap vs true model HTC ---
        gap = performance_gap(hlc_result, true_htc)
        true_band = hlc_to_epc_band(true_htc / floor_area)
        print(f"  [#13a] True HLC   : {true_htc:.1f} W/K  "
              f"({true_htc/floor_area:.3f} W/K/m2)  -> EPC band {true_band['band']}")
        print(f"  [#13a] Gap        : {gap['gap_pct']:+.1f}%  ({gap['interpretation']})")

        # --- Service #13b: rolling monthly EPC ---
        epc_series = rolling_epc(indoor, dwelling, floor_area,
                                 meta["property_type"], meta["build_era"])
        write_rolling_epc_csv(meter_num, epc_series)
        valid_months = [s for s in epc_series if s["band"]]
        if valid_months:
            bands      = [s["band"] for s in valid_months]
            band_counts = {b: bands.count(b) for b in sorted(set(bands))}
            print(f"  [#13b] Rolling EPC: {len(valid_months)} months  "
                  f"bands: {band_counts}")

        # --- Service #14: comfort vs cost ---
        comfort = comfort_cost_report(
            indoor, elec, gas, tariff, default_elec, GAS_RATE_P_KWH,
            WINTER_START, WINTER_END
        )
        print(f"\n  [#14] Window: {WINTER_START} to {WINTER_END}")
        print(f"  [#14] Total cost     : GBP {comfort['total_cost_gbp']:.2f}")
        print(f"  [#14] Vacant cost    : GBP {comfort['vacant_cost_gbp']:.2f} "
              f"({comfort['vacant_cost_pct']:.1f}% of total)")
        print(f"  [#14] Comfort score  : {comfort['pct_in_comfort_zone']:.1f}% "
              f"of occupied periods in 18-22C zone")
        print(f"  [#14] Cold periods   : {comfort['cold_occupied_periods']} "
              f"(occupied, below 18C)")
        if comfort["health_risk_periods"]:
            print(f"  [#14] HEALTH RISK    : {comfort['health_risk_periods']} "
                  f"periods below 16C while occupied")

        summary.append({
            "m":           meter_num,
            "label":       params["label"],
            "true_htc":    true_htc,
            "true_tau":    true_tau,
            "fit_tau":     tau_agg["tau_hours"],
            "fit_htc":     hlc_result["hlc_w_per_k"],
            "gap_pct":     gap["gap_pct"],
            "epc_true":    true_band["band"],
            "epc_fitted":  band_result["band"],
            "n_events":    len(good),
            "comfort_pct": comfort["pct_in_comfort_zone"],
            "vacant_pct":  comfort["vacant_cost_pct"],
            "cost_gbp":    comfort["total_cost_gbp"],
        })

    # --- Cross-meter summary table ---
    print(f"\n\n{'='*90}")
    print(f"SUMMARY TABLE   (regression window {REGRESSION_START} to {REGRESSION_END})")
    print(f"{'='*90}")
    header = (f"{'M':<3} {'Label':<30} {'HTC true':>8} {'HTC fit':>7} "
              f"{'Gap%':>6} {'Band':>5} {'Events':>7} "
              f"{'Comfort%':>9} {'Vacant%':>8} {'Cost GBP':>9}")
    print(header)
    print("-" * 90)
    for r in summary:
        if "status" in r:
            print(f"{r['m']:<3} insufficient data")
            continue
        print(f"{r['m']:<3} {r['label']:<30} "
              f"{r['true_htc']:>8.1f} {r['fit_htc']:>7.1f} "
              f"{r['gap_pct']:>+6.1f}% {r['epc_fitted']:>5}  "
              f"{r['n_events']:>7} "
              f"{r['comfort_pct']:>8.1f}% {r['vacant_pct']:>7.1f}% "
              f"{r['cost_gbp']:>9.2f}")
    print("=" * 90)

    # Write summary CSV
    fields = ["m", "label", "true_htc", "true_tau", "fit_tau", "fit_htc",
              "gap_pct", "epc_true", "epc_fitted", "n_events",
              "comfort_pct", "vacant_pct", "cost_gbp"]
    with open("data/tier4_summary.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(r for r in summary if "status" not in r)
    print(f"\nWritten: data/tier4_summary.csv")
    for n in METERS:
        print(f"         data/m{n}_tier4_events.csv")
        print(f"         data/m{n}_tier4_rolling_epc.csv")


if __name__ == "__main__":
    main()

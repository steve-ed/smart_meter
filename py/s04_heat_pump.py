"""
Service #4 — Heat Pump Suitability Scoring.

Run: python py/s04_heat_pump.py
Outputs: data/s04_heat_pump.csv
"""

import csv
import statistics
from datetime import datetime, date as date_type

from config import METERS, ELEC_METERS, GAS_RATE_P_KWH, ELEC_RATE_P_KWH
from tier1_lib import load_tariff_rates
from tier2_lib import load_consumption, load_weather

OUT_FILE          = "data/s04_heat_pump.csv"
BOILER_EFFICIENCY = 0.89
ETA_ASHP          = 0.45
GRANT_GBP         = 7500
INSTALLED_COST_GBP = 12000
DISCOUNT_RATE     = 0.035
NPV_YEARS         = 15
HEATING_SEASON_MONTHS = {10, 11, 12, 1, 2, 3}
SUMMER_MONTHS         = {5, 6, 7, 8, 9}


def cop_at_outdoor_temp(t_outdoor: float, flow_temp: float = 45.0,
                         eta: float = ETA_ASHP) -> float:
    if t_outdoor <= -10.0:
        return 1.0
    t_out_k  = t_outdoor + 273.15
    t_flow_k = flow_temp  + 273.15
    if t_flow_k <= t_out_k:
        return 6.0
    return eta * t_flow_k / (t_flow_k - t_out_k)


def estimate_base_load(daily_gas: dict) -> float:
    summer = [kwh for d, kwh in daily_gas.items() if d.month in SUMMER_MONTHS]
    if len(summer) < 14:
        return 3.0
    return statistics.median(summer)


def heating_kwh(total_daily_kwh: float, base_load_kwh: float) -> float:
    return max(total_daily_kwh - base_load_kwh, 0.0)


def heat_pump_payback(installed_cost_gbp: float,
                       annual_saving_gbp: float,
                       grant_gbp: float = GRANT_GBP,
                       discount_rate: float = DISCOUNT_RATE) -> dict:
    net_cost = max(installed_cost_gbp - grant_gbp, 0.0)
    if annual_saving_gbp <= 0:
        return {
            "installed_cost_gbp": installed_cost_gbp,
            "grant_gbp":          grant_gbp,
            "net_cost_gbp":       round(net_cost, 0),
            "annual_saving_gbp":  round(annual_saving_gbp, 2),
            "payback_years":      None,
            "npv_15yr_gbp":       None,
            "viable":             False,
        }
    simple_payback = net_cost / annual_saving_gbp
    npv_15 = sum(annual_saving_gbp / (1 + discount_rate) ** t
                 for t in range(1, NPV_YEARS + 1)) - net_cost
    return {
        "installed_cost_gbp": installed_cost_gbp,
        "grant_gbp":          grant_gbp,
        "net_cost_gbp":       round(net_cost, 0),
        "annual_saving_gbp":  round(annual_saving_gbp, 2),
        "payback_years":      round(simple_payback, 1),
        "npv_15yr_gbp":       round(npv_15, 0),
        "viable":             simple_payback <= 15 and npv_15 > 0,
    }


def suitability_flags(result: dict) -> list[dict]:
    return [
        {
            "check": "annual_heating_demand",
            "pass":  result["heating_gas_kwh"] >= 5000,
            "value": result["heating_gas_kwh"],
            "note":  "Below 5,000 kWh/year heating demand, payback extends significantly.",
        },
        {
            "check": "seasonal_signal",
            "pass":  result.get("winter_summer_gas_ratio", 1.0) >= 2.0,
            "value": result.get("winter_summer_gas_ratio"),
            "note":  "Low seasonal variation may indicate gas is primarily for hot water.",
        },
        {
            "check": "cop_above_breakeven",
            "pass":  (result["mean_seasonal_cop"] is not None and
                      result["mean_seasonal_cop"] >= result.get("breakeven_cop", 4.0)),
            "value": result["mean_seasonal_cop"],
            "note":  "If COP is below electricity/gas price ratio, HP costs more to run.",
        },
        {
            "check": "financial_viability",
            "pass":  result.get("viable", False),
            "value": result.get("payback_years"),
            "note":  "Payback should be under 15 years for a reasonable investment case.",
        },
    ]


def _build_daily_gas(meter_id: int) -> dict[date_type, float]:
    rows = load_consumption(meter_id)
    daily: dict[date_type, float] = {}
    for r in rows:
        d = date_type.fromisoformat(r["timestamp"][:10])
        daily[d] = daily.get(d, 0.0) + r["gas_kwh"]
    return daily


def _build_daily_weather() -> dict[date_type, float]:
    daily_temps: dict[date_type, list[float]] = {}
    for r in load_weather():
        if r.get("is_forecast"):
            continue
        d = date_type.fromisoformat(r["timestamp"][:10])
        daily_temps.setdefault(d, []).append(r["temp_c"])
    return {d: sum(v) / len(v) for d, v in daily_temps.items()}


def _model_scenario(daily_gas: dict, daily_weather: dict,
                     base_load: float, elec_period_rates: dict,
                     flow_temp: float) -> dict:
    gas_cost_p = hp_cost_p = 0.0
    heating_gas_kwh_total = hp_elec_kwh_total = 0.0

    for d, total_gas in sorted(daily_gas.items()):
        if d not in daily_weather:
            continue
        h_kwh = heating_kwh(total_gas, base_load)
        if h_kwh <= 0:
            continue
        t_outdoor = daily_weather[d]
        cop       = cop_at_outdoor_temp(t_outdoor, flow_temp)
        thermal   = h_kwh * BOILER_EFFICIENCY
        elec_kwh  = thermal / cop
        midday_rate = elec_period_rates.get(24, ELEC_RATE_P_KWH)
        gas_cost_p            += h_kwh    * GAS_RATE_P_KWH
        hp_cost_p             += elec_kwh * midday_rate
        heating_gas_kwh_total += h_kwh
        hp_elec_kwh_total     += elec_kwh

    n_days = len([d for d in daily_gas if d in daily_weather])
    scale  = 365 / n_days if n_days > 0 else 1.0

    gas_annual_gbp = gas_cost_p            * scale / 100
    hp_annual_gbp  = hp_cost_p             * scale / 100
    hg_annual      = heating_gas_kwh_total * scale
    he_annual      = hp_elec_kwh_total     * scale
    saving         = gas_annual_gbp - hp_annual_gbp
    mean_cop       = (hg_annual * BOILER_EFFICIENCY / he_annual) if he_annual > 0 else None

    return {
        "heating_gas_kwh":   round(hg_annual, 0),
        "gas_cost_gbp":      round(gas_annual_gbp, 2),
        "hp_elec_kwh":       round(he_annual, 0),
        "hp_elec_cost_gbp":  round(hp_annual_gbp, 2),
        "annual_saving_gbp": round(saving, 2),
        "mean_seasonal_cop": round(mean_cop, 2) if mean_cop else None,
    }


def analyse_meter(meter_id: int, daily_weather: dict) -> list[dict]:
    daily_gas = _build_daily_gas(meter_id)
    base_load = estimate_base_load(daily_gas)
    mpan      = ELEC_METERS[meter_id]
    elec_rates, _ = load_tariff_rates(mpan)
    breakeven_cop = ELEC_RATE_P_KWH / GAS_RATE_P_KWH

    winter_daily = [v for d, v in daily_gas.items() if d.month in HEATING_SEASON_MONTHS]
    summer_daily = [v for d, v in daily_gas.items() if d.month in SUMMER_MONTHS]
    ws_ratio = ((sum(winter_daily) / len(winter_daily)) /
                (sum(summer_daily) / len(summer_daily))) if summer_daily else 1.0

    rows = []
    for scenario, flow_temp in [("optimistic_45c_flow", 45.0), ("conservative_55c_flow", 55.0)]:
        model   = _model_scenario(daily_gas, daily_weather, base_load, elec_rates, flow_temp)
        payback = heat_pump_payback(INSTALLED_COST_GBP, model["annual_saving_gbp"])
        result  = {
            **model,
            "breakeven_cop":           round(breakeven_cop, 2),
            "winter_summer_gas_ratio": round(ws_ratio, 2),
            **{k: payback[k] for k in ["payback_years", "npv_15yr_gbp", "viable"]},
        }
        flags = suitability_flags(result)
        flag_dict = {f["check"]: f["pass"] for f in flags}

        print(f"  M{meter_id} [{scenario}]: saving=£{model['annual_saving_gbp']:.2f}  "
              f"cop={model['mean_seasonal_cop']}  breakeven={breakeven_cop:.1f}  "
              f"payback={payback['payback_years']}yr  viable={payback['viable']}")

        rows.append({
            "meter_id":                 meter_id,
            "scenario":                 scenario,
            "heating_gas_kwh":          model["heating_gas_kwh"],
            "hp_elec_kwh":              model["hp_elec_kwh"],
            "gas_cost_gbp":             model["gas_cost_gbp"],
            "hp_elec_cost_gbp":         model["hp_elec_cost_gbp"],
            "annual_saving_gbp":        model["annual_saving_gbp"],
            "mean_seasonal_cop":        model["mean_seasonal_cop"],
            "breakeven_cop":            round(breakeven_cop, 2),
            "payback_years":            payback["payback_years"],
            "npv_15yr_gbp":             payback["npv_15yr_gbp"],
            "viable":                   payback["viable"],
            "flag_heating_demand":      flag_dict["annual_heating_demand"],
            "flag_seasonal_signal":     flag_dict["seasonal_signal"],
            "flag_cop_above_breakeven": flag_dict["cop_above_breakeven"],
            "flag_financial_viability": flag_dict["financial_viability"],
        })
    return rows


def main():
    print("Service #4 — Heat Pump Suitability Scoring\n")
    daily_weather = _build_daily_weather()
    all_rows = []
    for meter_id in sorted(METERS):
        all_rows.extend(analyse_meter(meter_id, daily_weather))

    fields = [
        "meter_id", "scenario", "heating_gas_kwh", "hp_elec_kwh",
        "gas_cost_gbp", "hp_elec_cost_gbp", "annual_saving_gbp",
        "mean_seasonal_cop", "breakeven_cop", "payback_years", "npv_15yr_gbp",
        "viable", "flag_heating_demand", "flag_seasonal_signal",
        "flag_cop_above_breakeven", "flag_financial_viability",
    ]
    with open(OUT_FILE, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows([{f: r.get(f, "") for f in fields} for r in all_rows])
    print(f"\nWrote {len(all_rows)} rows to {OUT_FILE}")


if __name__ == "__main__":
    main()

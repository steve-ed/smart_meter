import sys
import os
import re
import json
import time
import subprocess
import tempfile

import streamlit as st

sys.path.insert(0, "py")

import s01_tariff_matching as s01
import s02_battery_sizing as s02
import s03_disaggregation as s03
import s04_heat_pump as s04
import s05_boiler_trending as s05
import s06_heating_efficiency as s06
import s07_budget_forecast as s07
import s09_prewarm as s09
import s10_leak_frost as s10
import s11_anomaly_suppression as s11
import tier4_analysis as t4

from app_utils import parse_pytest_summary, _rewrite_constant
from tier2_lib import load_weather
from tier3_lib import load_labeled_days

import importlib
import config as _cfg
importlib.reload(_cfg)
from tier1_lib import load_solar_generation, compute_annual_export
from config import (
    METER_META,
    GAS_RATE_P_KWH, ELEC_RATE_P_KWH,
    SOLAR_METERS, SEG_RATE_P_KWH,
    WINTER_START, WINTER_END,
    REGRESSION_START, REGRESSION_END,
)

st.set_page_config(page_title="Smart Meter Dashboard", layout="wide")

st.markdown("""
<style>
  /* Base font size +25% */
  html, body, [class*="css"] { font-size: 1.25rem !important; }

  /* Dataframe: larger text, stronger contrast */
  .stDataFrame table { font-size: 1.1rem !important; }
  .stDataFrame th {
    font-size: 1.1rem !important;
    color: #ffffff !important;
    background-color: #1a3a5c !important;
    font-weight: 700 !important;
  }
  .stDataFrame td { color: #0d0d0d !important; }

  /* Checkbox ticks in dataframes */
  .stDataFrame input[type="checkbox"] { transform: scale(1.4); accent-color: #1a7a3c; }

  /* Expander headers */
  .streamlit-expanderHeader { font-size: 1.15rem !important; font-weight: 600 !important; color: #0d0d0d !important; }

  /* Tab labels */
  .stTabs [data-baseweb="tab"] { font-size: 1.1rem !important; font-weight: 600 !important; }
  .stTabs [aria-selected="true"] { color: #032147 !important; border-bottom: 3px solid #209dd7 !important; }

  /* Sidebar text */
  .css-1d391kg, section[data-testid="stSidebar"] { font-size: 1.1rem !important; }

  /* Metric values */
  [data-testid="stMetricValue"] { font-size: 1.6rem !important; font-weight: 700 !important; color: #032147 !important; }
  [data-testid="stMetricLabel"] { font-size: 1.0rem !important; color: #444444 !important; }

  /* Caption text */
  .stCaption { font-size: 0.95rem !important; color: #333333 !important; }
</style>
""", unsafe_allow_html=True)

# ── Session state defaults ──────────────────────────────────────────────────

def _init_state():
    defaults = {
        "results":          {},
        "pytest_output":    "",
        "pytest_passed":    None,
        "pytest_counts":    (0, 0),
        "pytest_duration":  0.0,
        "last_run_meter":   None,
        "last_run_time":    None,
        "is_running":       False,
        "pending_services": [],
        "shared_inputs":    None,
        "run_meter_id":     None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()

# ── Pytest runner ────────────────────────────────────────────────────────────

def run_pytest(counter_placeholder=None) -> bool:
    """Run full test suite. Returns True if all pass. Updates session_state."""
    t0 = time.time()
    proc = subprocess.Popen(
        [sys.executable, "-m", "pytest", "-v", "tests/"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )

    lines = []
    done = 0
    total = 0
    for line in proc.stdout:
        lines.append(line)
        if not total:
            m = re.search(r"collected (\d+) item", line)
            if m:
                total = int(m.group(1))
        if any(tag in line for tag in ("PASSED", "FAILED", "ERROR")):
            done += 1
            if counter_placeholder and total:
                counter_placeholder.progress(done / total, text=f"Tests: {done} / {total}")

    proc.wait()
    duration = round(time.time() - t0, 1)
    output = "".join(lines)
    passed, failed = parse_pytest_summary(output)

    st.session_state.pytest_output = output
    st.session_state.pytest_passed = (proc.returncode == 0)
    st.session_state.pytest_counts = (passed, failed)
    st.session_state.pytest_duration = duration
    return proc.returncode == 0

# ── Service runner ───────────────────────────────────────────────────────────

def _to_rows(result) -> list[dict]:
    """Wrap a single dict result in a list for uniform table display."""
    if isinstance(result, dict):
        return [result]
    return result or []


ALL_SERVICE_KEYS = [
    "s13", "s13b", "s13c", "s14",
    "s01", "s02", "s03", "s04",
    "s05", "s06", "s07", "s08", "s09", "s10",
    "s11",
]


def _load_shared_inputs(meter_id: int) -> dict | None:
    try:
        with open("data/eon_tariffs.json") as f:
            eon_products = json.load(f)
        daily_weather = s04._build_daily_weather()
        weather_rows  = load_weather()
        all_days      = load_labeled_days(meter_id, weeks=16)
        inputs = {
            "eon_products": eon_products,
            "daily_weather": daily_weather,
            "weather_rows": weather_rows,
            "all_days": all_days,
        }

        # Tier 4 — indoor temperature and consumption
        try:
            from config import METERS as _GAS, REGRESSION_START, REGRESSION_END, WINTER_START, WINTER_END
            mpan   = _GAS[meter_id]
            indoor = t4.load_indoor(meter_id)
            inputs["tier4"] = {
                "indoor":      indoor,
                "gas":         t4.load_consumption(mpan, "gas",        REGRESSION_START, REGRESSION_END),
                "elec":        t4.load_consumption(mpan, "electricity", WINTER_START,     WINTER_END),
                "tariff":      t4.load_tariff(mpan),
                "precomputed": None,  # populated lazily by S13
            }
        except Exception as _e4:
            inputs["tier4"] = {"error": str(_e4)}

        return inputs
    except Exception as e:
        st.error(f"Failed to load service dependencies: {e}")
        return None


def _run_single_service(key: str, meter_id: int, inputs: dict) -> list[dict]:
    try:
        if key == "s01":
            return _to_rows(s01.analyse_meter(meter_id, inputs["eon_products"]))
        if key == "s02":
            return _to_rows(s02.analyse_meter(meter_id))
        if key == "s03":
            return _to_rows(s03.analyse_meter(meter_id))
        if key == "s04":
            return _to_rows(s04.analyse_meter(meter_id, inputs["daily_weather"]))
        if key == "s05":
            return _to_rows(s05.analyse_meter(meter_id))
        if key == "s06":
            return _to_rows(s06.analyse_meter(meter_id))
        if key == "s07":
            return _to_rows(s07.analyse_meter(meter_id))
        if key == "s08":
            return _run_s08(meter_id)
        if key == "s09":
            return _to_rows(s09.analyse_meter(meter_id))
        if key == "s10":
            return _to_rows(s10.analyse_meter(meter_id, inputs["weather_rows"]))
        if key == "s11":
            return _to_rows(s11.analyse_meter(meter_id, inputs["all_days"]))
        if key in ("s13", "s13b", "s13c", "s14"):
            return _run_tier4(key, meter_id, inputs)
        return []
    except Exception as e:
        return [{"error": str(e)}]


def _run_tier4(key: str, meter_id: int, inputs: dict) -> list[dict]:
    t4_in = inputs.get("tier4")
    if not t4_in:
        return [{"error": "Indoor temperature data not available for this meter"}]
    if "error" in t4_in:
        return [{"error": f"Tier 4 load failed: {t4_in['error']}"}]

    from config import (METERS as _GAS, METER_META,
                        ELEC_RATE_P_KWH, GAS_RATE_P_KWH,
                        WINTER_START, WINTER_END)

    mpan       = _GAS[meter_id]
    params     = t4.DWELLING_PARAMS[meter_id]
    meta       = METER_META[meter_id]
    dwelling   = t4.build_dwelling(params)
    floor_area = params["total_floor_area_m2"]

    precomputed = t4_in.get("precomputed")

    if key == "s13":
        rows = []
        for mode, overnight in [("all_hours", False), ("overnight_only", True)]:
            r = t4.analyse_meter(meter_id, mpan, t4_in["indoor"], t4_in["gas"],
                                 t4_in["elec"], t4_in["tariff"], overnight,
                                 precomputed=precomputed)
            if r:
                epc = t4.hlc_to_epc_band(r["fit_htc"] / floor_area)
                rows.append({
                    "meter_id":         meter_id,
                    "mode":             mode,
                    "fit_tau_h":        r["fit_tau"],
                    "true_tau_h":       r["true_tau"],
                    "fit_hlc_w_per_k":  r["fit_htc"],
                    "true_htc_w_per_k": r["true_htc"],
                    "epc_fitted":       r["epc_fitted"],
                    "epc_score":        epc["epc_score"],
                    "epc_band_best":    r.get("epc_band_best", ""),
                    "epc_band_worst":   r.get("epc_band_worst", ""),
                    "confidence":       r.get("confidence", ""),
                    "epc_true":         r["epc_true"],
                    "gap_pct":          r["gap_pct"],
                    "interpretation":   r["interp"],
                    "n_events":         r["n_events"],
                })
            else:
                rows.append({"meter_id": meter_id, "mode": mode,
                             "status": "insufficient_events"})
        return rows

    if key == "s13b":
        series = t4.rolling_epc(t4_in["indoor"], dwelling, floor_area,
                                meta["property_type"], meta["build_era"],
                                overnight_only=True, precomputed=precomputed)
        rows = []
        for s in series:
            row = {"meter_id": meter_id, **s}
            if s.get("status") == "ok" and s.get("hlc_w_per_k"):
                epc = t4.hlc_to_epc_band(s["hlc_w_per_k"] / floor_area)
                row["epc_score"] = epc["epc_score"]
            rows.append(row)
        return rows

    if key == "s13c":
        base_load = t4.estimate_base_load(t4_in["gas"])
        runs      = t4.find_heating_runs(t4_in["indoor"], t4_in["gas"], base_load)
        result    = t4.heating_phase_regression(runs, floor_area)
        if not result:
            return [{"meter_id": meter_id, "status": "insufficient_heating_runs"}]
        epc = t4.hlc_to_epc_band(result["hlc_w_per_k"] / floor_area)
        return [{"meter_id": meter_id,
                 "epc_band":       epc["band"],
                 "epc_score":      epc["epc_score"],
                 "epc_band_best":  result.get("epc_band_best", ""),
                 "epc_band_worst": result.get("epc_band_worst", ""),
                 "confidence":     result.get("confidence", ""),
                 **result}]

    if key == "s14":
        result = t4.comfort_cost_report(
            t4_in["indoor"], t4_in["elec"], t4_in["gas"], t4_in["tariff"],
            ELEC_RATE_P_KWH, GAS_RATE_P_KWH, WINTER_START, WINTER_END,
        )
        return [{"meter_id": meter_id, **result}]

    return []


def _run_s08(meter_id: int) -> list[dict]:
    """s08 has no analyse_meter — replicate its per-meter logic here."""
    from s08_carbon_shifting import (
        fetch_carbon_intensity, optimal_shift_window, load_appliances,
        CARBON_REGION_ID,
    )
    appliances = [a for a in load_appliances() if a["meter_id"] == meter_id]
    try:
        carbon_periods = fetch_carbon_intensity(CARBON_REGION_ID)
    except Exception as e:
        return [{"error": str(e), "meter_id": meter_id}]

    rows = []
    for appl in appliances:
        result = optimal_shift_window(carbon_periods, appl)
        if result.get("recommendation") is None:
            continue
        rows.append({
            "meter_id":                    meter_id,
            "appliance":                   appl["appliance"],
            "recommended_start_time":      result["recommended_start_time"],
            "mean_carbon_gco2_per_kwh":    result["mean_carbon_gco2_per_kwh"],
            "current_carbon_gco2_per_kwh": result["current_carbon_gco2_per_kwh"],
            "carbon_saving_gco2":          result["carbon_saving_gco2"],
            "joint_optimal":               result["joint_optimal"],
        })
    return rows

SERVICE_NAMES = {
    "s01": "S01 — E.ON Tariff Comparison",
    "s02": "S02 — Battery Size Optimisation",
    "s03": "S03 — Appliance Disaggregation",
    "s04": "S04 — Heat Pump Suitability",
    "s05": "S05 — Boiler Efficiency Trending",
    "s06": "S06 — Heating Efficiency Scoring",
    "s07": "S07 — Degree-Day Budget Forecast",
    "s08": "S08 — Carbon-Aware Demand Shifting",
    "s09": "S09 — Heating Pre-Warm Optimisation",
    "s10": "S10 — Micro-Leak & Frost Detection",
    "s11": "S11 — Vacancy-Aware Anomaly Suppression",
    "s13":  "S13 — EPC from Temperature Decay",
    "s13b": "S13b — Rolling Monthly EPC Band",
    "s13c": "S13c — Heating-Phase HLC Regression",
    "s14":  "S14 — Comfort vs Cost",
}

def _meter_utilities() -> dict[int, list[str]]:
    """Return {meter_id: ['electricity', 'gas']} derived from config."""
    from config import METERS as _GAS, ELEC_METERS as _ELEC
    all_ids = set(_GAS) | set(_ELEC)
    return {
        mid: sorted(
            (["electricity"] if mid in _ELEC else []) +
            (["gas"]         if mid in _GAS  else [])
        )
        for mid in all_ids
    }

UTILITY_ICONS = {"electricity": "Electric", "gas": "Gas"}

# ── Sidebar ─────────────────────────────────────────────────────────────────

def _meter_label(mid: int, meta: dict) -> str:
    base = f"M{mid} — {meta['property_type'].capitalize()}"
    if "build_year" in meta:
        return f"{base} ({meta['build_year']})"
    return f"{base} ({meta['build_era'].replace('_', ' ')})"

METER_LABELS = {mid: _meter_label(mid, meta) for mid, meta in METER_META.items()}

with st.sidebar:
    st.markdown("## ⚡ Smart Meter")
    st.divider()

    selected_label = st.selectbox(
        "Select Meter",
        options=list(METER_LABELS.values()),
        index=0,
    )
    meter_id = next((mid for mid, lbl in METER_LABELS.items() if lbl == selected_label), 1)

    utils = _meter_utilities().get(meter_id, [])
    badge_html = " &nbsp; ".join(
        f'<span style="background:#1a7a3c;color:#fff;padding:2px 10px;border-radius:12px;font-size:0.9rem;font-weight:600">{UTILITY_ICONS[u]}</span>'
        if u == "electricity" else
        f'<span style="background:#c45c00;color:#fff;padding:2px 10px;border-radius:12px;font-size:0.9rem;font-weight:600">{UTILITY_ICONS[u]}</span>'
        for u in utils
    )
    st.markdown(badge_html or "_No data found_", unsafe_allow_html=True)
    st.divider()

    run_clicked = st.button("▶ Run All", use_container_width=True, type="primary")

    if run_clicked:
        counter_ph = st.empty()
        st.info("Running tests (~50s)…")
        tests_ok = run_pytest(counter_ph)
        counter_ph.empty()
        if not tests_ok:
            st.sidebar.error("Tests failed — services not run")
        else:
            inputs = _load_shared_inputs(meter_id)
            if inputs:
                st.session_state.results = {}
                st.session_state.is_running = True
                st.session_state.pending_services = list(ALL_SERVICE_KEYS)
                st.session_state.shared_inputs = inputs
                st.session_state.run_meter_id = meter_id
                st.session_state.last_run_meter = meter_id
                st.session_state.last_run_time = time.strftime("%Y-%m-%d %H:%M")
                st.rerun()

    st.divider()
    st.markdown("**Last Run**")

    if st.session_state.last_run_time is None:
        st.caption("No run yet")
    else:
        passed, failed = st.session_state.pytest_counts
        color = "green" if failed == 0 else "red"
        st.markdown(f":{color}[✓ Tests {passed}/{passed + failed}]")

        results = st.session_state.results
        done = len(results)
        total = len(ALL_SERVICE_KEYS)
        if st.session_state.is_running:
            next_key = st.session_state.pending_services[0] if st.session_state.pending_services else ""
            st.caption(f"Running {SERVICE_NAMES.get(next_key, '')}…")
            st.progress(done / total)
        else:
            tier1 = sum(1 for k in ["s01", "s02", "s03", "s04"] if k in results)
            tier2 = sum(1 for k in ["s05", "s06", "s07", "s08", "s09", "s10"] if k in results)
            tier3 = sum(1 for k in ["s11"] if k in results)
            st.markdown(f":green[✓ Tier 1 {tier1}/4]")
            st.markdown(f":green[✓ Tier 2 {tier2}/6]")
            st.markdown(f":green[✓ Tier 3 {tier3}/1]")
            st.caption(st.session_state.last_run_time)

# ── Display helpers ──────────────────────────────────────────────────────────

def _show_service(key: str) -> None:
    name = SERVICE_NAMES[key]
    results = st.session_state.results
    has_run = key in results

    label = f"{'✓' if has_run else '○'} {name}"
    with st.expander(label, expanded=has_run):
        if not has_run:
            st.caption("Not yet run.")
            return
        rows = results[key]
        if not rows:
            st.caption("No results returned.")
            return
        if "error" in rows[0]:
            st.error(rows[0]["error"])
            return
        st.dataframe(rows, use_container_width=True)


# ── Consumption summary ──────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def _consumption_summary(meter_id: int, gas_rate: float, elec_rate: float,
                          today_ym: str) -> list[dict]:
    """
    Monthly gas + electricity kWh and cost for the last 12 complete months,
    plus a totals row.  Cache key includes rates and today_ym so it
    invalidates correctly when config is saved or midnight passes.
    """
    from config import METERS as _GAS, ELEC_METERS as _ELEC
    from tier4_analysis import load_consumption

    wide_start = "2020-01-01"
    wide_end   = "2099-12-31"

    gas_raw  = load_consumption(_GAS[meter_id],  "gas",         wide_start, wide_end) if meter_id in _GAS  else {}
    elec_raw = load_consumption(_ELEC[meter_id], "electricity", wide_start, wide_end) if meter_id in _ELEC else {}

    monthly_gas:  dict[str, float] = {}
    monthly_elec: dict[str, float] = {}
    for ts, kwh in gas_raw.items():
        monthly_gas[ts[:7]]  = monthly_gas.get(ts[:7], 0.0)  + kwh
    for ts, kwh in elec_raw.items():
        monthly_elec[ts[:7]] = monthly_elec.get(ts[:7], 0.0) + kwh

    is_solar = meter_id in SOLAR_METERS
    monthly_solar_gen:    dict[str, float] = {}
    monthly_solar_export: dict[str, float] = {}

    if is_solar:
        from datetime import datetime as _dt
        gen_rows = load_solar_generation(meter_id)
        cons_map = {ts: kwh for ts, kwh in elec_raw.items()}
        for g in gen_rows:
            ym   = g["timestamp"][:7]
            gen  = g["solar_kwh"]
            cons = cons_map.get(g["timestamp"], 0.0)
            monthly_solar_gen[ym]    = monthly_solar_gen.get(ym, 0.0)    + gen
            monthly_solar_export[ym] = monthly_solar_export.get(ym, 0.0) + max(0.0, gen - cons)

    all_months = sorted(set(monthly_gas) | set(monthly_elec))
    last_12 = [m for m in all_months if m < today_ym][-12:]

    rows = []
    for ym in last_12:
        gas_kwh  = monthly_gas.get(ym, 0.0)
        elec_kwh = monthly_elec.get(ym, 0.0)
        gas_gbp  = round(gas_kwh  * gas_rate  / 100, 2)
        elec_gbp = round(elec_kwh * elec_rate / 100, 2)
        row = {
            "month":          ym,
            "gas_kwh":        round(gas_kwh, 1),
            "gas_cost_gbp":   gas_gbp,
            "elec_kwh":       round(elec_kwh, 1),
            "elec_cost_gbp":  elec_gbp,
            "total_cost_gbp": round(gas_gbp + elec_gbp, 2),
        }
        if is_solar:
            sol_kwh = monthly_solar_gen.get(ym, 0.0)
            exp_kwh = monthly_solar_export.get(ym, 0.0)
            row["solar_kwh"]        = round(sol_kwh, 1)
            row["export_kwh"]       = round(exp_kwh, 1)
            row["seg_earnings_gbp"] = round(exp_kwh * SEG_RATE_P_KWH / 100, 2)
        rows.append(row)

    if rows:
        total_row = {
            "month":          "TOTAL",
            "gas_kwh":        round(sum(r["gas_kwh"]        for r in rows), 1),
            "gas_cost_gbp":   round(sum(r["gas_cost_gbp"]   for r in rows), 2),
            "elec_kwh":       round(sum(r["elec_kwh"]       for r in rows), 1),
            "elec_cost_gbp":  round(sum(r["elec_cost_gbp"]  for r in rows), 2),
            "total_cost_gbp": round(sum(r["total_cost_gbp"] for r in rows), 2),
        }
        if is_solar:
            total_row["solar_kwh"]        = round(sum(r.get("solar_kwh", 0.0)        for r in rows), 1)
            total_row["export_kwh"]       = round(sum(r.get("export_kwh", 0.0)       for r in rows), 1)
            total_row["seg_earnings_gbp"] = round(sum(r.get("seg_earnings_gbp", 0.0) for r in rows), 2)
        rows.append(total_row)

    return rows


# ── Config helpers ───────────────────────────────────────────────────────────



def _atomic_write(path: str, content: str) -> None:
    dir_ = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(dir=dir_, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)
    except Exception:
        os.unlink(tmp)
        raise


def save_config(gas_rate: float, elec_rate: float,
                winter_start: str, winter_end: str,
                reg_start: str, reg_end: str) -> None:
    path = "py/config.py"
    with open(path) as f:
        content = f.read()
    for name, value in [
        ("GAS_RATE_P_KWH",   gas_rate),
        ("ELEC_RATE_P_KWH",  elec_rate),
        ("WINTER_START",     winter_start),
        ("WINTER_END",       winter_end),
        ("REGRESSION_START", reg_start),
        ("REGRESSION_END",   reg_end),
    ]:
        content = _rewrite_constant(content, name, value)
    _atomic_write(path, content)


def save_tariffs(tariffs: list[dict]) -> None:
    _atomic_write("data/eon_tariffs.json", json.dumps(tariffs, indent=2))


# ── Main tabs ────────────────────────────────────────────────────────────────

tab_t1, tab_t2, tab_t3, tab_t4, tab_tests, tab_cfg = st.tabs(
    ["Tier 1", "Tier 2", "Tier 3", "Tier 4", "Tests", "Config"]
)

with tab_t1:
    st.markdown(f"### Tier 1 — Smart Energy Services")
    st.caption(f"Consumption: M{meter_id}" +
               (f"  |  Service results: M{st.session_state.last_run_meter}"
                if st.session_state.last_run_meter and st.session_state.last_run_meter != meter_id
                else ""))

    with st.expander("Monthly Consumption — Gas & Electricity", expanded=True):
        try:
            summary = _consumption_summary(
                meter_id, GAS_RATE_P_KWH, ELEC_RATE_P_KWH,
                time.strftime("%Y-%m"),
            )
            if summary:
                st.dataframe(summary, use_container_width=True, hide_index=True)
            else:
                st.caption("No consumption data available for this meter.")
        except Exception as _e:
            st.caption(f"Could not load consumption summary: {_e}")

    for key in ["s01", "s02", "s03", "s04"]:
        _show_service(key)

with tab_t2:
    st.markdown("### Tier 2 — Weather & Efficiency Services")
    if st.session_state.last_run_meter:
        st.caption(f"Results for M{st.session_state.last_run_meter}")
    for key in ["s05", "s06", "s07", "s08", "s09", "s10"]:
        _show_service(key)

with tab_t3:
    st.markdown("### Tier 3 — Anomaly Detection")
    if st.session_state.last_run_meter:
        st.caption(f"Results for M{st.session_state.last_run_meter}")
    _show_service("s11")

with tab_t4:
    st.markdown("### Tier 4 — Building Physics & EPC")
    if st.session_state.last_run_meter:
        st.caption(f"Results for M{st.session_state.last_run_meter}")
    for key in ["s13", "s13b", "s13c", "s14"]:
        _show_service(key)

with tab_tests:
    st.markdown("### Test Results")

    if st.session_state.pytest_passed is None:
        st.info("Press **Run All** to execute the test suite.")
    else:
        passed, failed = st.session_state.pytest_counts
        duration = st.session_state.pytest_duration

        col1, col2, col3 = st.columns(3)
        col1.metric("Passed", passed, delta=None)
        col2.metric("Failed", failed, delta=None)
        col3.metric("Duration", f"{duration}s")

        if failed > 0:
            st.error(f"{failed} test(s) failed — services were not run.")
        else:
            st.success("All tests passed.")

        with st.expander("Full pytest output", expanded=failed > 0):
            st.code(st.session_state.pytest_output, language="text")

with tab_cfg:
    st.markdown("### Configuration")

    # Read current tariffs from file (always fresh)
    with open("data/eon_tariffs.json") as f:
        tariffs = json.load(f)

    col_left, col_right = st.columns(2)

    with col_left:
        import config as _live_cfg
        st.markdown("#### Energy Rates")
        new_gas  = st.number_input("Gas Rate (p/kWh)",  value=float(_live_cfg.GAS_RATE_P_KWH),  step=0.1, format="%.2f")
        new_elec = st.number_input("Electricity Rate (p/kWh)", value=float(_live_cfg.ELEC_RATE_P_KWH), step=0.1, format="%.2f")

        st.markdown("#### Analysis Window")
        new_winter_start = st.text_input("Winter Start (YYYY-MM-DD)", value=_live_cfg.WINTER_START)
        new_winter_end   = st.text_input("Winter End (YYYY-MM-DD)",   value=_live_cfg.WINTER_END)
        new_reg_start    = st.text_input("Regression Start (YYYY-MM-DD)", value=_live_cfg.REGRESSION_START)
        new_reg_end      = st.text_input("Regression End (YYYY-MM-DD)",   value=_live_cfg.REGRESSION_END)

    with col_right:
        st.markdown("#### E.ON Tariffs")
        updated_tariffs = []
        for product in tariffs:
            with st.expander(product["name"]):
                if product["product_type"] == "actual":
                    st.caption("Uses actual meter rates — no editable bands.")
                    updated_tariffs.append(product)
                    continue

                new_standing = st.number_input(
                    "Standing (p/day)",
                    value=float(product["standing_p_day"] or 0.0),
                    step=0.5, format="%.2f",
                    key=f"standing_{product['name']}",
                )
                updated_bands = []
                for i, band in enumerate(product["bands"]):
                    new_rate = st.number_input(
                        f"Band {i+1} rate p/kWh  (periods {band['start_period']}–{band['end_period']})",
                        value=float(band["rate_p_per_kwh"]),
                        step=0.1, format="%.2f",
                        key=f"rate_{product['name']}_{i}",
                    )
                    updated_bands.append({**band, "rate_p_per_kwh": new_rate})
                updated_tariffs.append({
                    **product,
                    "standing_p_day": new_standing,
                    "bands": updated_bands,
                })

    if st.session_state.get("_config_saved"):
        st.session_state._config_saved = False
        st.toast("Configuration saved.", icon="✅")

    if st.button("💾 Save Changes"):
        save_config(new_gas, new_elec,
                    new_winter_start, new_winter_end,
                    new_reg_start, new_reg_end)
        save_tariffs(updated_tariffs)
        import importlib, config as _cfg
        importlib.reload(_cfg)
        st.session_state._config_saved = True
        st.rerun()

# ── Incremental service execution ────────────────────────────────────────────

if st.session_state.is_running and st.session_state.pending_services:
    next_key = st.session_state.pending_services[0]
    result = _run_single_service(
        next_key,
        st.session_state.run_meter_id,
        st.session_state.shared_inputs,
    )
    st.session_state.results[next_key] = result
    st.session_state.pending_services = st.session_state.pending_services[1:]
    if not st.session_state.pending_services:
        st.session_state.is_running = False
        st.session_state.shared_inputs = None
    st.rerun()

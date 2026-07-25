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

from tier2_lib import load_weather
from tier3_lib import load_labeled_days

from config import (
    METER_META,
    GAS_RATE_P_KWH, ELEC_RATE_P_KWH,
    WINTER_START, WINTER_END,
    REGRESSION_START, REGRESSION_END,
)

st.set_page_config(page_title="Smart Meter Dashboard", layout="wide")

# ── Session state defaults ──────────────────────────────────────────────────

def _init_state():
    defaults = {
        "results":       {},     # {service_key: list[dict]}
        "pytest_output": "",
        "pytest_passed": None,
        "pytest_counts": (0, 0),
        "pytest_duration": 0.0,
        "last_run_meter": None,
        "last_run_time":  None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()

# ── Pytest runner ────────────────────────────────────────────────────────────

def parse_pytest_summary(output: str) -> tuple[int, int]:
    passed = int(m.group(1)) if (m := re.search(r"(\d+) passed", output)) else 0
    failed = int(m.group(1)) if (m := re.search(r"(\d+) failed", output)) else 0
    return passed, failed


def run_pytest() -> bool:
    """Run full test suite. Returns True if all pass. Updates session_state."""
    t0 = time.time()
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-v", "tests/"],
        capture_output=True,
        text=True,
    )
    duration = round(time.time() - t0, 1)
    output = proc.stdout + proc.stderr
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


def run_services(meter_id: int) -> None:
    """Run all 11 services for one meter. Updates st.session_state.results."""
    results = {}

    # Pre-compute shared inputs
    try:
        with open("data/eon_tariffs.json") as f:
            eon_products = json.load(f)
        daily_weather = s04._build_daily_weather()
        weather_rows  = load_weather()
        all_days      = load_labeled_days(meter_id, weeks=16)
    except Exception as e:
        st.error(f"Failed to load service dependencies: {e}")
        return

    # Tier 1
    results["s01"] = _to_rows(s01.analyse_meter(meter_id, eon_products))
    results["s02"] = _to_rows(s02.analyse_meter(meter_id))
    results["s03"] = _to_rows(s03.analyse_meter(meter_id))
    results["s04"] = _to_rows(s04.analyse_meter(meter_id, daily_weather))

    # Tier 2
    results["s05"] = _to_rows(s05.analyse_meter(meter_id))
    results["s06"] = _to_rows(s06.analyse_meter(meter_id))
    results["s07"] = _to_rows(s07.analyse_meter(meter_id))
    results["s08"] = _run_s08(meter_id)
    results["s09"] = _to_rows(s09.analyse_meter(meter_id))
    results["s10"] = _to_rows(s10.analyse_meter(meter_id, weather_rows))

    # Tier 3
    results["s11"] = _to_rows(s11.analyse_meter(meter_id, all_days))

    st.session_state.results = results


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

# ── Sidebar ─────────────────────────────────────────────────────────────────

METER_LABELS = {
    mid: f"M{mid} — {meta['property_type'].capitalize()} ({meta['build_era'].replace('_', ' ')})"
    for mid, meta in METER_META.items()
}

with st.sidebar:
    st.markdown("## ⚡ Smart Meter")
    st.divider()

    selected_label = st.selectbox(
        "Select Meter",
        options=list(METER_LABELS.values()),
        index=0,
    )
    meter_id = next((mid for mid, lbl in METER_LABELS.items() if lbl == selected_label), 1)

    run_clicked = st.button("▶ Run All", use_container_width=True, type="primary")

    if run_clicked:
        with st.spinner("Running tests…"):
            tests_ok = run_pytest()
        if not tests_ok:
            st.sidebar.error("Tests failed — services not run")
        else:
            with st.spinner(f"Running services for M{meter_id}…"):
                run_services(meter_id)
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
        tier1 = sum(1 for k in ["s01", "s02", "s03", "s04"] if k in results)
        tier2 = sum(1 for k in ["s05", "s06", "s07", "s08", "s09", "s10"] if k in results)
        tier3 = sum(1 for k in ["s11"] if k in results)
        st.markdown(f":green[✓ Tier 1 {tier1}/4]")
        st.markdown(f":green[✓ Tier 2 {tier2}/6]")
        st.markdown(f":green[✓ Tier 3 {tier3}/1]")
        st.caption(st.session_state.last_run_time)

# ── Display helpers ──────────────────────────────────────────────────────────

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
}


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


# ── Config helpers ───────────────────────────────────────────────────────────

def _rewrite_constant(content: str, name: str, value) -> str:
    """Replace the value of a constant in config.py content, preserving comments."""
    val_str = f'"{value}"' if isinstance(value, str) else f"{value:.10g}"
    return re.sub(
        rf'^({re.escape(name)}\s*=\s*)("[^"]*"|\d+\.?\d*)',
        rf'\g<1>{val_str}',
        content,
        flags=re.MULTILINE,
    )


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

tab_t1, tab_t2, tab_t3, tab_tests, tab_cfg = st.tabs(
    ["Tier 1", "Tier 2", "Tier 3", "Tests", "Config"]
)

with tab_t1:
    st.markdown(f"### Tier 1 — Smart Energy Services")
    if st.session_state.last_run_meter:
        st.caption(f"Results for M{st.session_state.last_run_meter}")
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
        st.markdown("#### Energy Rates")
        new_gas  = st.number_input("Gas Rate (p/kWh)",  value=float(GAS_RATE_P_KWH),  step=0.1, format="%.2f")
        new_elec = st.number_input("Electricity Rate (p/kWh)", value=float(ELEC_RATE_P_KWH), step=0.1, format="%.2f")

        st.markdown("#### Analysis Window")
        new_winter_start = st.text_input("Winter Start (YYYY-MM-DD)", value=WINTER_START)
        new_winter_end   = st.text_input("Winter End (YYYY-MM-DD)",   value=WINTER_END)
        new_reg_start    = st.text_input("Regression Start (YYYY-MM-DD)", value=REGRESSION_START)
        new_reg_end      = st.text_input("Regression End (YYYY-MM-DD)",   value=REGRESSION_END)

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

    if st.button("💾 Save Changes"):
        save_config(new_gas, new_elec,
                    new_winter_start, new_winter_end,
                    new_reg_start, new_reg_end)
        save_tariffs(updated_tariffs)
        st.success("Saved.")
        st.rerun()

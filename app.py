import sys
import io
import re
import json
import time
import subprocess
from contextlib import redirect_stdout

import streamlit as st

sys.path.insert(0, "py")

import s01_tariff_matching as s01
import s02_battery_sizing as s02
import s03_disaggregation as s03
import s04_heat_pump as s04
import s05_boiler_trending as s05
import s06_heating_efficiency as s06
import s07_budget_forecast as s07
import s08_carbon_shifting as s08
import s09_prewarm as s09
import s10_leak_frost as s10
import s11_anomaly_suppression as s11

from tier2_lib import load_weather
from tier3_lib import load_labeled_days

from config import (
    METERS, METER_META,
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
    with open("data/eon_tariffs.json") as f:
        eon_products = json.load(f)

    daily_weather = s04._build_daily_weather()
    weather_rows  = load_weather()
    all_days      = load_labeled_days(meter_id, weeks=16)

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

# ── Main tabs ────────────────────────────────────────────────────────────────

tab_t1, tab_t2, tab_t3, tab_tests, tab_cfg = st.tabs(
    ["Tier 1", "Tier 2", "Tier 3", "Tests", "Config"]
)

with tab_t1:
    st.write("Tier 1 — coming soon")

with tab_t2:
    st.write("Tier 2 — coming soon")

with tab_t3:
    st.write("Tier 3 — coming soon")

with tab_tests:
    st.write("Tests — coming soon")

with tab_cfg:
    st.write("Config — coming soon")

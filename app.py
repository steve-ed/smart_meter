import sys
import io
import re
import json
import time
import subprocess
from contextlib import redirect_stdout
from datetime import date

import streamlit as st

sys.path.insert(0, "py")

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
    meter_id = next(mid for mid, lbl in METER_LABELS.items() if lbl == selected_label)

    run_clicked = st.button("▶ Run All", use_container_width=True, type="primary")

    st.divider()
    st.markdown("**Last Run**")

    if st.session_state.last_run_time is None:
        st.caption("No run yet")
    else:
        passed, failed = st.session_state.pytest_counts
        color = "green" if failed == 0 else "red"
        st.markdown(f":{color}[✓ Tests {passed}/{passed + failed}]")

        results = st.session_state.results
        tier1 = sum(1 for k in ["s01","s02","s03","s04"] if k in results)
        tier2 = sum(1 for k in ["s05","s06","s07","s08","s09","s10"] if k in results)
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

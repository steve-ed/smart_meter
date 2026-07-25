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

st.write("# ⚡ Smart Meter Dashboard")
st.write("Skeleton loaded OK")

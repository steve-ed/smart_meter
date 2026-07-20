# Anomaly Detection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a rule-based anomaly detector and Streamlit dashboard that flags spikes, prolonged elevated usage, and flat-lines across 15 MPxNs of half-hourly electricity and gas data.

**Architecture:** `anomaly_detector.py` contains all detection logic (pure functions, no UI dependency). `dashboard.py` loads `data/consumption_clean.csv`, calls the detector at startup, caches both results, and renders a filterable Streamlit UI with summary cards, a Plotly timeline, and an events table.

**Tech Stack:** Python 3, pandas, plotly, streamlit, pytest

---

## File Map

| File | Role |
|---|---|
| `anomaly_detector.py` | Detection logic — spikes, prolonged, flat-line |
| `dashboard.py` | Streamlit UI — filters, cards, chart, table |
| `requirements.txt` | Pinned dependencies |
| `tests/test_anomaly_detector.py` | Unit tests for all detector functions |

---

## Task 1: Install dependencies and scaffold tests

**Files:**
- Create: `requirements.txt`
- Create: `tests/__init__.py`
- Create: `tests/test_anomaly_detector.py`

- [ ] **Step 1: Create requirements.txt**

```
pandas
plotly
streamlit
pytest
```

- [ ] **Step 2: Install dependencies**

```bash
pip install -r requirements.txt
```

Expected: all packages install without error.

- [ ] **Step 3: Create tests/__init__.py**

Create an empty file at `tests/__init__.py`.

- [ ] **Step 4: Create test file with helper only**

Create `tests/test_anomaly_detector.py`:

```python
import pandas as pd
import pytest
from anomaly_detector import (
    detect_anomalies,
    _detect_spikes,
    _detect_prolonged,
    _detect_flatlines,
    BASELINE_DAYS,
    _HALFHOURS_PER_DAY,
)


def make_group(values, mpxn="TEST", utility="electricity", start="2021-01-01"):
    """Build a minimal DataFrame matching the format detect_anomalies expects."""
    timestamps = pd.date_range(start=start, periods=len(values), freq="30min")
    return pd.DataFrame({
        "mpxn": mpxn,
        "utility": utility,
        "timestamp": timestamps,
        "value": [float(v) for v in values],
    })
```

- [ ] **Step 5: Confirm pytest discovers the file (no tests yet)**

```bash
pytest tests/ -v
```

Expected: `no tests ran` — zero failures, no import errors.

- [ ] **Step 6: Commit**

```bash
git add requirements.txt tests/__init__.py tests/test_anomaly_detector.py
git commit -m "chore: add dependencies and test scaffold"
```

---

## Task 2: Spike detection

**Files:**
- Create: `anomaly_detector.py`
- Modify: `tests/test_anomaly_detector.py`

- [ ] **Step 1: Write failing spike tests**

Append to `tests/test_anomaly_detector.py`:

```python
def test_spike_detects_value_above_threshold():
    # 28 days of baseline at 1.0, then one reading at 10.0 (10× baseline — exceeds 3×)
    baseline = [1.0] * (BASELINE_DAYS * _HALFHOURS_PER_DAY)
    group = make_group(baseline + [10.0])
    events = _detect_spikes(group, "TEST", "electricity")
    assert len(events) == 1
    assert events[0]["anomaly_type"] == "spike"
    assert events[0]["value"] == 10.0
    assert events[0]["ratio"] == pytest.approx(10.0, rel=0.01)


def test_spike_does_not_flag_normal_reading():
    readings = [1.0] * (BASELINE_DAYS * _HALFHOURS_PER_DAY + 1)
    group = make_group(readings)
    events = _detect_spikes(group, "TEST", "electricity")
    assert len(events) == 0


def test_spike_skips_when_insufficient_baseline():
    # Only 5 readings — below the min_periods threshold
    group = make_group([1.0, 1.0, 1.0, 1.0, 100.0])
    events = _detect_spikes(group, "TEST", "electricity")
    assert len(events) == 0


def test_spike_excludes_zeros_from_gas_baseline():
    # Gas: baseline of alternating 0 and 2.0; spike at 20.0
    # Mean of non-zero values = 2.0; 20.0 / 2.0 = 10× > 3× threshold
    baseline = ([0.0, 2.0] * (BASELINE_DAYS * _HALFHOURS_PER_DAY // 2))
    group = make_group(baseline + [20.0], utility="gas")
    events = _detect_spikes(group, "TEST", "gas")
    assert len(events) == 1
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_anomaly_detector.py -v -k "spike"
```

Expected: `ImportError: cannot import name '_detect_spikes' from 'anomaly_detector'` (or ModuleNotFoundError).

- [ ] **Step 3: Create anomaly_detector.py with spike detection**

Create `anomaly_detector.py`:

```python
import pandas as pd

SPIKE_MULTIPLIER     = 3.0
PROLONGED_MULTIPLIER = 2.0
PROLONGED_MIN_DAYS   = 3
FLATLINE_HOURS       = 24
BASELINE_DAYS        = 28
_HALFHOURS_PER_DAY   = 48


def detect_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    """
    Accepts a DataFrame with columns: mpxn, utility, timestamp (datetime64), value (float).
    Returns a DataFrame of anomaly events with columns:
    mpxn, utility, anomaly_type, timestamp, value, baseline, ratio.
    """
    results = []
    for (mpxn, utility), group in df.groupby(["mpxn", "utility"]):
        group = group.sort_values("timestamp").reset_index(drop=True)
        results.extend(_detect_spikes(group, mpxn, utility))
        results.extend(_detect_prolonged(group, mpxn, utility))
        results.extend(_detect_flatlines(group, mpxn, utility))

    cols = ["mpxn", "utility", "anomaly_type", "timestamp", "value", "baseline", "ratio"]
    if not results:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(results)[cols].sort_values("timestamp").reset_index(drop=True)


def _rolling_mean(series: pd.Series, exclude_zeros: bool = False) -> pd.Series:
    window = BASELINE_DAYS * _HALFHOURS_PER_DAY
    if exclude_zeros:
        return series.where(series > 0).rolling(window, min_periods=window // 2).mean()
    return series.rolling(window, min_periods=window // 2).mean()


def _detect_spikes(group: pd.DataFrame, mpxn: str, utility: str) -> list:
    exclude_zeros = utility == "gas"
    baseline = _rolling_mean(group["value"], exclude_zeros=exclude_zeros)
    mask = (group["value"] > baseline * SPIKE_MULTIPLIER) & baseline.notna()
    events = []
    for idx in group[mask].index:
        b = baseline[idx]
        v = group.at[idx, "value"]
        events.append({
            "mpxn": mpxn, "utility": utility, "anomaly_type": "spike",
            "timestamp": group.at[idx, "timestamp"],
            "value": round(v, 4), "baseline": round(b, 4), "ratio": round(v / b, 2),
        })
    return events


def _detect_prolonged(group: pd.DataFrame, mpxn: str, utility: str) -> list:
    pass


def _detect_flatlines(group: pd.DataFrame, mpxn: str, utility: str) -> list:
    pass
```

- [ ] **Step 4: Run spike tests to confirm they pass**

```bash
pytest tests/test_anomaly_detector.py -v -k "spike"
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add anomaly_detector.py tests/test_anomaly_detector.py
git commit -m "feat: add spike detection"
```

---

## Task 3: Prolonged elevated usage detection

**Files:**
- Modify: `anomaly_detector.py`
- Modify: `tests/test_anomaly_detector.py`

- [ ] **Step 1: Write failing prolonged tests**

Append to `tests/test_anomaly_detector.py`:

```python
def test_prolonged_detects_three_consecutive_elevated_days():
    # 28 days baseline at 1.0/HH (48/day), then 4 days at 3.0/HH (144/day = 3× baseline daily)
    baseline = [1.0] * (BASELINE_DAYS * _HALFHOURS_PER_DAY)
    elevated = [3.0] * (4 * _HALFHOURS_PER_DAY)
    group = make_group(baseline + elevated)
    events = _detect_prolonged(group, "TEST", "electricity")
    assert len(events) == 1
    assert events[0]["anomaly_type"] == "prolonged"
    assert events[0]["ratio"] >= 2.0


def test_prolonged_does_not_flag_two_consecutive_elevated_days():
    baseline = [1.0] * (BASELINE_DAYS * _HALFHOURS_PER_DAY)
    elevated = [3.0] * (2 * _HALFHOURS_PER_DAY)
    group = make_group(baseline + elevated)
    events = _detect_prolonged(group, "TEST", "electricity")
    assert len(events) == 0


def test_prolonged_does_not_flag_with_insufficient_baseline():
    # Only 10 days of data — below min_periods for the rolling window
    group = make_group([1.0] * (10 * _HALFHOURS_PER_DAY))
    events = _detect_prolonged(group, "TEST", "electricity")
    assert len(events) == 0
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_anomaly_detector.py -v -k "prolonged"
```

Expected: 3 tests FAIL (function returns None, not a list).

- [ ] **Step 3: Implement _detect_prolonged**

Replace the `_detect_prolonged` stub in `anomaly_detector.py`:

```python
def _detect_prolonged(group: pd.DataFrame, mpxn: str, utility: str) -> list:
    daily = group.set_index("timestamp")["value"].resample("D").sum()
    baseline = daily.rolling(BASELINE_DAYS, min_periods=BASELINE_DAYS // 2).mean()
    elevated = (daily > baseline * PROLONGED_MULTIPLIER) & baseline.notna()

    events = []
    run_start = None
    run_len = 0
    for date, is_elevated in elevated.items():
        if is_elevated:
            if run_start is None:
                run_start = date
            run_len += 1
        else:
            if run_len >= PROLONGED_MIN_DAYS:
                b = float(baseline[run_start])
                v = float(daily[run_start])
                events.append({
                    "mpxn": mpxn, "utility": utility, "anomaly_type": "prolonged",
                    "timestamp": pd.Timestamp(run_start),
                    "value": round(v, 4), "baseline": round(b, 4), "ratio": round(v / b, 2),
                })
            run_start = None
            run_len = 0

    if run_len >= PROLONGED_MIN_DAYS:
        b = float(baseline[run_start])
        v = float(daily[run_start])
        events.append({
            "mpxn": mpxn, "utility": utility, "anomaly_type": "prolonged",
            "timestamp": pd.Timestamp(run_start),
            "value": round(v, 4), "baseline": round(b, 4), "ratio": round(v / b, 2),
        })
    return events
```

- [ ] **Step 4: Run prolonged tests to confirm they pass**

```bash
pytest tests/test_anomaly_detector.py -v -k "prolonged"
```

Expected: 3 tests PASS.

- [ ] **Step 5: Run all tests to confirm nothing broken**

```bash
pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add anomaly_detector.py tests/test_anomaly_detector.py
git commit -m "feat: add prolonged elevated usage detection"
```

---

## Task 4: Flat-line detection

**Files:**
- Modify: `anomaly_detector.py`
- Modify: `tests/test_anomaly_detector.py`

- [ ] **Step 1: Write failing flat-line tests**

Append to `tests/test_anomaly_detector.py`:

```python
def test_flatline_detects_24_consecutive_zero_hours():
    # 24 hours = 48 half-hours of zeros, surrounded by non-zero readings
    normal = [1.0] * _HALFHOURS_PER_DAY
    zeros  = [0.0] * _HALFHOURS_PER_DAY   # exactly 24 hours
    group = make_group(normal + zeros + [1.0] * 10)
    events = _detect_flatlines(group, "TEST", "electricity")
    assert len(events) == 1
    assert events[0]["anomaly_type"] == "flat_line"
    assert events[0]["value"] == 0.0
    assert events[0]["baseline"] is None


def test_flatline_does_not_flag_short_zero_run():
    normal = [1.0] * _HALFHOURS_PER_DAY
    zeros  = [0.0] * 10   # only 5 hours
    group = make_group(normal + zeros + [1.0] * 10)
    events = _detect_flatlines(group, "TEST", "electricity")
    assert len(events) == 0


def test_flatline_detects_run_at_end_of_series():
    normal = [1.0] * _HALFHOURS_PER_DAY
    zeros  = [0.0] * _HALFHOURS_PER_DAY
    group = make_group(normal + zeros)
    events = _detect_flatlines(group, "TEST", "electricity")
    assert len(events) == 1


def test_flatline_detects_multiple_separate_runs():
    normal = [1.0] * _HALFHOURS_PER_DAY
    zeros  = [0.0] * _HALFHOURS_PER_DAY
    group = make_group(zeros + normal + zeros)
    events = _detect_flatlines(group, "TEST", "electricity")
    assert len(events) == 2
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_anomaly_detector.py -v -k "flatline"
```

Expected: 4 tests FAIL (function returns None, not a list).

- [ ] **Step 3: Implement _detect_flatlines**

Replace the `_detect_flatlines` stub in `anomaly_detector.py`:

```python
def _detect_flatlines(group: pd.DataFrame, mpxn: str, utility: str) -> list:
    min_consecutive = FLATLINE_HOURS * 2  # convert hours to half-hours
    events = []
    run_start_idx = None
    run_len = 0
    for i, val in enumerate(group["value"]):
        if val == 0.0:
            if run_start_idx is None:
                run_start_idx = i
            run_len += 1
        else:
            if run_len >= min_consecutive:
                events.append({
                    "mpxn": mpxn, "utility": utility, "anomaly_type": "flat_line",
                    "timestamp": group.at[run_start_idx, "timestamp"],
                    "value": 0.0, "baseline": None, "ratio": None,
                })
            run_start_idx = None
            run_len = 0
    if run_len >= min_consecutive:
        events.append({
            "mpxn": mpxn, "utility": utility, "anomaly_type": "flat_line",
            "timestamp": group.at[run_start_idx, "timestamp"],
            "value": 0.0, "baseline": None, "ratio": None,
        })
    return events
```

- [ ] **Step 4: Run flat-line tests to confirm they pass**

```bash
pytest tests/test_anomaly_detector.py -v -k "flatline"
```

Expected: 4 tests PASS.

- [ ] **Step 5: Run all tests**

```bash
pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add anomaly_detector.py tests/test_anomaly_detector.py
git commit -m "feat: add flat-line detection"
```

---

## Task 5: Wire up detect_anomalies and verify full API

**Files:**
- Modify: `tests/test_anomaly_detector.py`

- [ ] **Step 1: Write failing integration tests**

Append to `tests/test_anomaly_detector.py`:

```python
def test_detect_anomalies_returns_correct_columns():
    baseline = [1.0] * (BASELINE_DAYS * _HALFHOURS_PER_DAY)
    df = make_group(baseline + [10.0])
    result = detect_anomalies(df)
    assert set(result.columns) == {
        "mpxn", "utility", "anomaly_type", "timestamp", "value", "baseline", "ratio"
    }


def test_detect_anomalies_returns_empty_dataframe_when_no_anomalies():
    df = make_group([1.0] * 100)
    result = detect_anomalies(df)
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 0


def test_detect_anomalies_handles_multiple_mpxns():
    baseline = [1.0] * (BASELINE_DAYS * _HALFHOURS_PER_DAY)
    df1 = make_group(baseline + [10.0], mpxn="AAA")
    df2 = make_group(baseline + [10.0], mpxn="BBB")
    df = pd.concat([df1, df2], ignore_index=True)
    result = detect_anomalies(df)
    assert set(result["mpxn"].unique()) == {"AAA", "BBB"}
    assert len(result) == 2


def test_detect_anomalies_sorted_by_timestamp():
    baseline = [1.0] * (BASELINE_DAYS * _HALFHOURS_PER_DAY)
    df = make_group(baseline + [10.0, 1.0, 10.0])
    result = detect_anomalies(df)
    assert list(result["timestamp"]) == sorted(result["timestamp"])
```

- [ ] **Step 2: Run to confirm they pass (detect_anomalies already implemented)**

```bash
pytest tests/test_anomaly_detector.py -v -k "detect_anomalies"
```

Expected: 4 tests PASS.

- [ ] **Step 3: Run full test suite**

```bash
pytest tests/ -v
```

Expected: all tests PASS. Note the total count in the summary line.

- [ ] **Step 4: Commit**

```bash
git add tests/test_anomaly_detector.py
git commit -m "test: add integration tests for detect_anomalies"
```

---

## Task 6: Build Streamlit dashboard

**Files:**
- Create: `dashboard.py`

- [ ] **Step 1: Create dashboard.py**

Create `dashboard.py`:

```python
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from anomaly_detector import detect_anomalies

st.set_page_config(page_title="Energy Anomaly Monitor", layout="wide")


@st.cache_data
def load_data() -> pd.DataFrame:
    df = pd.read_csv("data/consumption_clean.csv")
    df["timestamp"] = pd.to_datetime(df["timestamp"], format="%Y-%m-%d %H:%M")
    return df


@st.cache_data
def get_anomalies(_df: pd.DataFrame) -> pd.DataFrame:
    # Underscore prefix tells Streamlit not to hash this arg.
    # Result is computed once at startup and cached for the session.
    return detect_anomalies(_df)


df = load_data()
anomalies = get_anomalies(df)

# ── Sidebar ────────────────────────────────────────────────────────────────────
st.sidebar.title("Filters")

mpxn = st.sidebar.selectbox("MPxN", sorted(df["mpxn"].unique()))

available_utilities = sorted(df[df["mpxn"] == mpxn]["utility"].unique().tolist())
utility_opts = ["both"] + available_utilities
utility = st.sidebar.selectbox("Utility", utility_opts)

anomaly_type = st.sidebar.selectbox(
    "Anomaly type", ["all", "spike", "prolonged", "flat_line"]
)

# ── Filter anomalies ───────────────────────────────────────────────────────────
filtered = anomalies[anomalies["mpxn"] == mpxn].copy()
if utility != "both":
    filtered = filtered[filtered["utility"] == utility]
if anomaly_type != "all":
    filtered = filtered[filtered["anomaly_type"] == anomaly_type]

# ── Summary cards ──────────────────────────────────────────────────────────────
st.title(f"Energy Anomaly Monitor — {mpxn}")

col1, col2, col3 = st.columns(3)
col1.metric("Spikes",     int((filtered["anomaly_type"] == "spike").sum()))
col2.metric("Prolonged",  int((filtered["anomaly_type"] == "prolonged").sum()))
col3.metric("Flat-lines", int((filtered["anomaly_type"] == "flat_line").sum()))

# ── Timeline chart ─────────────────────────────────────────────────────────────
st.subheader("Consumption timeline")

consumption = df[df["mpxn"] == mpxn].copy()
if utility != "both":
    consumption = consumption[consumption["utility"] == utility]

daily = (
    consumption
    .assign(date=consumption["timestamp"].dt.date)
    .groupby(["date", "utility"])["value"]
    .sum()
    .reset_index()
)

UTILITY_COLOURS = {"electricity": "#209dd7", "gas": "#753991"}
MARKER_COLOURS  = {"spike": "red", "prolonged": "orange", "flat_line": "gray"}
MARKER_LABELS   = {"spike": "Spike", "prolonged": "Prolonged", "flat_line": "Flat-line"}

fig = go.Figure()

for u, u_daily in daily.groupby("utility"):
    fig.add_trace(go.Scatter(
        x=u_daily["date"],
        y=u_daily["value"],
        name=u.capitalize(),
        line=dict(color=UTILITY_COLOURS.get(u, "#888888")),
    ))

y_max = daily["value"].max() if not daily.empty else 1.0
for atype, agroup in filtered.groupby("anomaly_type"):
    fig.add_trace(go.Scatter(
        x=agroup["timestamp"].dt.date,
        y=[y_max * 0.95] * len(agroup),
        mode="markers",
        name=MARKER_LABELS.get(atype, atype),
        marker=dict(
            color=MARKER_COLOURS.get(atype, "black"),
            size=10,
            symbol="triangle-down",
        ),
    ))

fig.update_layout(
    xaxis_title="Date",
    yaxis_title="Consumption",
    height=420,
    legend=dict(orientation="h", yanchor="bottom", y=1.02),
)
st.plotly_chart(fig, use_container_width=True)

# ── Events table ───────────────────────────────────────────────────────────────
st.subheader("Anomaly events")

if filtered.empty:
    st.info("No anomalies detected for the current selection.")
else:
    display = filtered.copy().sort_values("timestamp", ascending=False)
    display["ratio"]    = display["ratio"].apply(
        lambda x: f"{x:.1f}x" if pd.notna(x) else "-"
    )
    display["baseline"] = display["baseline"].apply(
        lambda x: f"{x:.3f}" if pd.notna(x) else "-"
    )
    display["timestamp"] = display["timestamp"].dt.strftime("%Y-%m-%d %H:%M")
    st.dataframe(
        display[["timestamp", "utility", "anomaly_type", "value", "baseline", "ratio"]],
        use_container_width=True,
        hide_index=True,
    )
```

- [ ] **Step 2: Run the dashboard**

```bash
streamlit run dashboard.py
```

Expected: browser opens at `http://localhost:8501`. The app loads (may take 30–60 seconds on first run while anomalies are computed for 2.37M rows).

- [ ] **Step 3: Verify each UI element manually**

Check the following in the browser:
- [ ] Summary cards show non-zero counts for at least one anomaly type on the default MPxN
- [ ] Changing MPxN in the sidebar updates all three sections
- [ ] Switching utility between electricity / gas / both changes the timeline
- [ ] Filtering by anomaly type updates both the cards and the events table
- [ ] Timeline chart is zoomable (drag to zoom, double-click to reset)
- [ ] Events table is sorted newest-first

- [ ] **Step 4: Commit**

```bash
git add dashboard.py
git commit -m "feat: add anomaly detection Streamlit dashboard"
```

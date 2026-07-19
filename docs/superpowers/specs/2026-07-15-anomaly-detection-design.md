# Anomaly Detection — Design Spec

**Date:** 2026-07-15
**Status:** Approved

---

## Overview

A consumer-facing Streamlit dashboard that detects and displays three classes of energy consumption anomaly — spikes, prolonged elevated usage, and flat-lining — across 15 MPxNs using rule-based thresholds against a rolling 28-day baseline.

---

## Architecture

Two files with a clean separation of concerns:

- **`anomaly_detector.py`** — pure detection logic. Accepts a pandas DataFrame of clean consumption data, returns an anomaly events DataFrame. No UI dependency; independently testable.
- **`dashboard.py`** — Streamlit app. Loads `data/consumption_clean.csv` and calls the detector at startup. Both the raw data and the anomaly results are cached with `@st.cache_data` so the UI filtering is instant.

```
data/consumption_clean.csv
        │
        ▼
anomaly_detector.py  ──►  anomalies DataFrame
        │                  (mpxn, utility, anomaly_type,
        │                   timestamp, value, baseline, ratio)
        ▼
dashboard.py  ──►  sidebar filters  ──►  charts + table
```

---

## Detection Rules

All rules use a **28-day rolling baseline** computed per MPxN + utility combination.

| Anomaly type | Rule | Threshold |
|---|---|---|
| **Spike** | Half-hourly value > N× rolling 28-day mean | 3× |
| **Prolonged** | Daily total > N× rolling 28-day daily mean for 3+ consecutive days | 2× |
| **Flat-line** | 24+ consecutive hours of zero readings | absolute zero |

**Baseline note:** gas zeros are excluded from the mean calculation. Gas reads zero for the majority of half-hours (no active flow), so including zeros would artificially suppress the baseline and generate false spike alerts.

Each detected event records:

| Field | Description |
|---|---|
| `mpxn` | Meter point number |
| `utility` | `electricity` or `gas` |
| `anomaly_type` | `spike`, `prolonged`, or `flat_line` |
| `timestamp` | Start of the anomalous event |
| `value` | Observed value (kWh or m³) |
| `baseline` | Rolling mean at the time of detection |
| `ratio` | `value ÷ baseline` — severity indicator |

Thresholds are named constants at the top of `anomaly_detector.py`:

```python
SPIKE_MULTIPLIER      = 3.0   # HH value must exceed baseline × this
PROLONGED_MULTIPLIER  = 2.0   # daily total must exceed baseline × this
PROLONGED_MIN_DAYS    = 3     # consecutive days required
FLATLINE_HOURS        = 24    # consecutive zero hours required
BASELINE_DAYS         = 28    # rolling window for mean
```

---

## Dashboard Layout

Single-page Streamlit app, no authentication, no persistence.

### Sidebar
- MPxN selector (dropdown of all 15 MPxNs)
- Utility selector (electricity / gas / both)
- Anomaly type filter (spike / prolonged / flat-line / all)

### Main Area

**1. Summary cards**
Three `st.metric` tiles showing the count of each anomaly type for the current filter selection.

**2. Timeline chart**
Daily consumption line chart (Plotly) with anomaly events overlaid as coloured markers:
- Red = spike
- Amber = prolonged
- Grey = flat-line

Chart is interactive and zoomable.

**3. Events table**
Sorted by timestamp descending. Columns: date, utility, anomaly type, value, baseline, ratio (formatted as "3.2×"). Rendered with `st.dataframe`.

---

## Data

- **Source:** `data/consumption_clean.csv` — 2,371,629 rows, pre-deduplicated, sentinel values removed.
- **Columns used:** `mpxn`, `utility`, `timestamp`, `value`, `unit`
- **Production data** (`production_clean.csv`) is out of scope for this prototype.

---

## Error Handling

- MPxNs with fewer than 28 days of data skip baseline-dependent rules (spike, prolonged) and only run flat-line detection.
- If a utility has no data for a selected MPxN, the dashboard shows a friendly "no data" message rather than an error.

---

## Out of Scope

- Push notifications or email alerts
- Authentication
- Gas production / solar data
- ML-based detection
- Historical anomaly persistence between sessions

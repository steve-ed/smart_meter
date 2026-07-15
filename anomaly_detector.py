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


def _detect_flatlines(group: pd.DataFrame, mpxn: str, utility: str) -> list:
    min_consecutive = FLATLINE_HOURS * 2  # hours to half-hours
    events = []
    run_start_idx = None
    run_len = 0
    for idx, val in group["value"].items():
        if val < 1e-9:
            if run_start_idx is None:
                run_start_idx = idx
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

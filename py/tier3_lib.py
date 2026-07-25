"""
Shared foundation for Tier 3 anomaly and pattern service scripts.
Not run directly — imported by s11_*.py and s12_*.py.
"""

from datetime import datetime, timedelta

from tier1_lib import load_electricity
from tier2_lib import load_weather
from occupancy_elec import ElecOccupancyDetector


def _daily_mean_temp(weather_rows: list[dict]) -> dict[str, float]:
    """
    Compute mean outdoor temperature per calendar date.
    weather_rows: output of load_weather() — half-hourly rows with 'timestamp' and 'temp_c'.
    Returns {date_str: mean_temp_c}.
    """
    buckets: dict[str, list[float]] = {}
    for row in weather_rows:
        date_str = row["timestamp"][:10]
        buckets.setdefault(date_str, []).append(row["temp_c"])
    return {d: sum(v) / len(v) for d, v in buckets.items()}


def load_labeled_days(
    meter_id: int,
    weeks: int = 16,
    elec_path: str = "data/consumption.csv",
    weather_path: str = "data/weather.csv",
) -> list[dict]:
    """
    Return a list of day-dicts for the most recent `weeks` weeks of complete
    electricity data, labeled with occupancy via ElecOccupancyDetector.

    Each dict:
      {
        "date":    str,        # "YYYY-MM-DD"
        "weekday": int,        # 0=Mon..6=Sun
        "periods": list[dict], # 48 items from ElecOccupancyDetector.add_day()
      }

    Callers slice as needed:
      analysis_days = all_days[-56:]   # last 8 weeks
      baseline_days = all_days[:-56]   # warm-up 8 weeks
    """
    readings = load_electricity(meter_id, path=elec_path)
    if not readings:
        return []

    weather_rows = load_weather(path=weather_path)
    daily_temp = _daily_mean_temp(weather_rows)

    # Determine window: most recent `weeks` complete weeks
    latest_ts = readings[-1]["timestamp"]
    latest_date = datetime.strptime(latest_ts[:10], "%Y-%m-%d").date()
    cutoff_date = latest_date - timedelta(weeks=weeks)

    # Group readings by date
    by_date: dict[str, list[float]] = {}
    for r in readings:
        d = r["timestamp"][:10]
        by_date.setdefault(d, []).append(r["elec_kwh"])

    # Collect dates in window with exactly 48 readings
    dates_in_window = sorted(
        d for d, vals in by_date.items()
        if len(vals) == 48
        and datetime.strptime(d, "%Y-%m-%d").date() > cutoff_date
    )

    if not dates_in_window:
        return []

    detector = ElecOccupancyDetector()
    result = []
    for date_str in dates_in_window:
        elec_48 = by_date[date_str]
        temp_c = daily_temp.get(date_str, 10.0)
        periods = detector.add_day(date_str, elec_48, temp_c)
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        result.append({
            "date": date_str,
            "weekday": dt.weekday(),
            "periods": periods,
        })
    return result

"""
Pull half-hourly outdoor temperature and wind speed from Open-Meteo.
Historical data comes from the archive API; the forecast API covers the last
7 days and the next 16 days.  Appends only missing dates to data/weather.csv.

Run:
    python weather.py                  # pull from START_DATE to today+16
    python weather.py --from 2024-01-01
"""

import argparse
import csv
import os
from datetime import date, datetime, timedelta

import requests
import urllib3

from config import LAT, LON, REGRESSION_START

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

OUT_FILE   = "data/weather.csv"
START_DATE = REGRESSION_START      # pull from two-winter regression window start
FIELDS     = ["timestamp", "temp_c", "wind_speed_ms", "is_forecast"]

ARCHIVE_URL  = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
HOURLY_VARS  = "temperature_2m,wind_speed_10m"
TIMEZONE     = "UTC"

# Archive API lags by ~5 days; use forecast API for recent + future
ARCHIVE_LAG_DAYS = 7


def existing_dates(path: str) -> set[str]:
    """Return set of date strings (YYYY-MM-DD) already present in the CSV."""
    if not os.path.exists(path):
        return set()
    dates = set()
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            dates.add(row["timestamp"][:10])
    return dates


def fetch(url: str, params: dict) -> dict:
    r = requests.get(url, params=params, timeout=30, verify=False)
    r.raise_for_status()
    return r.json()


def interpolate_to_half_hourly(times: list[str],
                                temps: list[float],
                                winds: list[float],
                                is_forecast: int) -> list[dict]:
    """
    Linear interpolation from hourly to half-hourly.
    Each hourly pair (i, i+1) produces two half-hour rows: HH:00 and HH:30.
    Temperature and wind at :30 are the midpoint between adjacent hours.
    """
    rows = []
    for i in range(len(times) - 1):
        if temps[i] is None or winds[i] is None:
            continue
        t0 = times[i]
        temp_00  = temps[i]
        wind_00  = winds[i]
        next_temp = temps[i + 1] if temps[i + 1] is not None else temps[i]
        next_wind = winds[i + 1] if winds[i + 1] is not None else winds[i]
        temp_30  = (temp_00 + next_temp) / 2
        wind_30  = (wind_00 + next_wind) / 2

        # HH:00 period
        rows.append({
            "timestamp":    t0.replace("T", " "),
            "temp_c":       round(temp_00, 2),
            "wind_speed_ms": round(wind_00 / 3.6, 2),  # km/h → m/s
            "is_forecast":  is_forecast,
        })
        # HH:30 period
        dt = datetime.strptime(t0, "%Y-%m-%dT%H:%M") + timedelta(minutes=30)
        rows.append({
            "timestamp":    dt.strftime("%Y-%m-%d %H:%M"),
            "temp_c":       round(temp_30, 2),
            "wind_speed_ms": round(wind_30 / 3.6, 2),
            "is_forecast":  is_forecast,
        })
    return rows


def pull_archive(start: date, end: date) -> list[dict]:
    if start > end:
        return []
    print(f"  archive  {start} to {end}")
    data = fetch(ARCHIVE_URL, {
        "latitude":   LAT,
        "longitude":  LON,
        "start_date": start.isoformat(),
        "end_date":   end.isoformat(),
        "hourly":     HOURLY_VARS,
        "timezone":   TIMEZONE,
        "wind_speed_unit": "kmh",
    })
    h = data["hourly"]
    return interpolate_to_half_hourly(h["time"], h["temperature_2m"],
                                      h["wind_speed_10m"], is_forecast=0)


def pull_forecast(start: date, end: date) -> list[dict]:
    if start > end:
        return []
    print(f"  forecast {start} to {end}")
    data = fetch(FORECAST_URL, {
        "latitude":    LAT,
        "longitude":   LON,
        "start_date":  start.isoformat(),
        "end_date":    end.isoformat(),
        "hourly":      HOURLY_VARS,
        "timezone":    TIMEZONE,
        "wind_speed_unit": "kmh",
    })
    h = data["hourly"]
    return interpolate_to_half_hourly(h["time"], h["temperature_2m"],
                                      h["wind_speed_10m"], is_forecast=1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--from", dest="start", default=START_DATE,
                        help="Start date YYYY-MM-DD (default: %(default)s)")
    args = parser.parse_args()

    pull_start = date.fromisoformat(args.start)
    today      = date.today()
    archive_end   = today - timedelta(days=ARCHIVE_LAG_DAYS)
    forecast_start = archive_end + timedelta(days=1)
    forecast_end  = today + timedelta(days=15)

    already = existing_dates(OUT_FILE)
    print(f"Existing dates in {OUT_FILE}: {len(already)}")

    # Find the first date not yet in the file for the archive range
    archive_fetch_start = pull_start
    while (archive_fetch_start <= archive_end and
           archive_fetch_start.isoformat() in already):
        archive_fetch_start += timedelta(days=1)

    rows = []

    if archive_fetch_start <= archive_end:
        rows += pull_archive(archive_fetch_start, archive_end)

    # Always refresh forecast window (prices/temps can be updated day-ahead)
    rows += pull_forecast(forecast_start, forecast_end)

    if not rows:
        print("Nothing new to write.")
        return

    # Deduplicate: skip timestamps already in file (archive overlap guard)
    new_rows = [r for r in rows if r["timestamp"][:10] not in already
                or r["is_forecast"] == 1]

    # For forecast rows, always overwrite (they update daily)
    # Load existing non-forecast rows, then merge
    existing_rows = []
    if os.path.exists(OUT_FILE):
        with open(OUT_FILE, newline="") as f:
            existing_rows = [r for r in csv.DictReader(f) if r["is_forecast"] == "0"]

    forecast_rows = [r for r in new_rows if r["is_forecast"] == 1]
    archive_rows  = [r for r in new_rows if r["is_forecast"] == 0]

    # Merge: existing non-forecast + new archive + new forecast
    all_rows = existing_rows + archive_rows + forecast_rows
    all_rows.sort(key=lambda r: r["timestamp"])

    # Deduplicate by timestamp, preferring is_forecast=0 (confirmed over forecast)
    seen: dict[str, dict] = {}
    for r in all_rows:
        ts = r["timestamp"]
        if ts not in seen or r["is_forecast"] in (0, "0"):
            seen[ts] = r

    final_rows = sorted(seen.values(), key=lambda r: r["timestamp"])

    with open(OUT_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(final_rows)

    n_archive  = sum(1 for r in final_rows if r["is_forecast"] in (0, "0"))
    n_forecast = sum(1 for r in final_rows if r["is_forecast"] in (1, "1"))
    print(f"\nWrote {len(final_rows):,} rows to {OUT_FILE}")
    print(f"  {n_archive:,} historical  |  {n_forecast:,} forecast")


if __name__ == "__main__":
    main()

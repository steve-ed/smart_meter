import json
import os
from datetime import date, timedelta

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

PVGIS_URL = "https://re.jrc.ec.europa.eu/api/v5_2/seriescalc"


def get_pvgis_profile(lat, lon, tilt=35, azimuth=180, year=2020, cache_dir="data"):
    """
    Fetch hourly PV generation from PVGIS for 1 kWp, interpolate to half-hourly.

    Returns:
        dict[date, list[48 floats]] — kWh per half-hour per kWp.
        Multiply by panel_kwp to get absolute generation.
    """
    cache_path = os.path.join(cache_dir, f"pvgis_cache_{lat}_{lon}_{year}.json")

    if os.path.exists(cache_path):
        with open(cache_path) as f:
            hourly = json.load(f)
    else:
        params = {
            "lat": lat,
            "lon": lon,
            "peakpower": 1.0,
            "angle": tilt,
            "aspect": azimuth - 180,  # PVGIS: 0=south, -90=east, 90=west
            "outputformat": "json",
            "pvcalculation": 1,
            "startyear": year,
            "endyear": year,
            "loss": 14,
        }
        r = requests.get(PVGIS_URL, params=params, timeout=30, verify=False)
        r.raise_for_status()
        data = r.json()
        hourly = [{"time": row["time"], "P": row["P"]}
                  for row in data["outputs"]["hourly"]]
        with open(cache_path, "w") as f:
            json.dump(hourly, f)

    # Convert: time="YYYYMMDD:HHMM", P in Watts for 1 kWp over 1 hour
    # → kWh per half-hour per kWp = P / 1000 / 2
    profile = {}
    for row in hourly:
        t = row["time"]
        d = date(int(t[0:4]), int(t[4:6]), int(t[6:8]))
        hour = int(t[9:11])
        kwh_per_hh = row["P"] / 1000 / 2
        slots = profile.setdefault(d, [0.0] * 48)
        slots[hour * 2] = kwh_per_hh
        slots[hour * 2 + 1] = kwh_per_hh

    return profile


import pandas as pd

STANDARD_YIELD_KWH_PER_KWP = 900.0


def get_measured_profile(data_dir, standard_yield=STANDARD_YIELD_KWH_PER_KWP):
    """
    Build a solar generation profile from real sandbox PV production data.

    Normalises the three sandbox PV MPXNs to a common annual yield
    (standard_yield kWh/kWp/yr), then averages their seasonal + diurnal shape.

    Returns:
        dict[date, list[48 floats]] — kWh per half-hour per kWp.
        Multiply by panel_kwp to get absolute generation.
    """
    path = os.path.join(data_dir, "solar_production.csv")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"{path} not found. Run pull_solar_production.py first."
        )

    df = pd.read_csv(path)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["month"] = df["timestamp"].dt.month
    df["slot"] = df["timestamp"].dt.hour * 2 + df["timestamp"].dt.minute // 30

    # Mean kWh per (month, slot) across all MPXNs — captures seasonal + diurnal shape
    shape_dict = df.groupby(["month", "slot"])["value_kwh"].mean().to_dict()

    # Compute implied annual total (mean shape × days in each month)
    days_in_month = {1:31, 2:28, 3:31, 4:30, 5:31, 6:30, 7:31, 8:31, 9:30, 10:31, 11:30, 12:31}
    annual_total = sum(
        shape_dict.get((m, s), 0.0) * days_in_month[m]
        for m in range(1, 13)
        for s in range(48)
    )

    # Scale so annual generation = standard_yield per kWp
    scale = standard_yield / annual_total if annual_total > 0 else 0.0

    # Build profile keyed by 2020 dates (leap year, so Feb 29 is valid)
    profile = {}
    d = date(2020, 1, 1)
    while d <= date(2020, 12, 31):
        profile[d] = [shape_dict.get((d.month, s), 0.0) * scale for s in range(48)]
        d += timedelta(days=1)

    return profile

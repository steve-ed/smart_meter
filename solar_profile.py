import json
import os
from datetime import date, timedelta

import requests

PVGIS_URL = "https://re.jrc.ec.europa.eu/api/v5_2/seriescalc"


def get_pvgis_profile(lat, lon, tilt=35, azimuth=180, year=2023, cache_dir="data"):
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
        r = requests.get(PVGIS_URL, params=params, timeout=30)
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

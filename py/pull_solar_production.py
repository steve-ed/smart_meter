"""
Pull electricity production data for the three sandbox PV MPXNs.
Saves to data/solar_production.csv. Run once before solar_analysis.py.
"""
import csv
import os
from datetime import datetime

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

API_KEY = "b2a7fc0f-56a1-4d71-8148-0644b1ee30c7"
BASE_URL = "https://api-v2-sandbox.data.n3rgy.com"
SOLAR_MPXNS = ["2234567891000", "5330642497188", "1234567891038"]
OUT_FILE = "data/solar_production.csv"
FIELDS = ["mpxn", "timestamp", "value_kwh"]

session = requests.Session()
session.headers["x-api-key"] = API_KEY
session.verify = False


def get(path, **params):
    r = session.get(f"{BASE_URL}{path}", params=params or None)
    r.raise_for_status()
    return r.json()


def iter_chunks(start_str, end_str, months=3):
    fmt = "%Y%m%d%H%M"
    cur = datetime.strptime(start_str, fmt)
    end = datetime.strptime(end_str, fmt)
    while cur < end:
        m = cur.month - 1 + months
        chunk_end = cur.replace(year=cur.year + m // 12, month=m % 12 + 1, day=1)
        chunk_end = min(chunk_end, end)
        yield cur.strftime(fmt), chunk_end.strftime(fmt)
        cur = chunk_end


def main():
    rows = []
    for mpxn in SOLAR_MPXNS:
        print(f"-- MPxN {mpxn}")
        meta = get(f"/mpxn/{mpxn}/utility/electricity/readingtype/production")
        cr = meta.get("availableCacheRange", {})
        if not cr.get("start") or not cr.get("end"):
            print("  no cache range, skipping")
            continue
        today = datetime.now().strftime("%Y%m%d%H%M")
        end = min(cr["end"], today)
        print(f"  production  ({cr['start']} to {end})")
        for chunk_start, chunk_end in iter_chunks(cr["start"], end):
            data = get(
                f"/mpxn/{mpxn}/utility/electricity/readingtype/production",
                start=chunk_start,
                end=chunk_end,
            )
            count = 0
            for device in data.get("devices", []):
                for v in device.get("values", []):
                    rows.append({
                        "mpxn": mpxn,
                        "timestamp": v["timestamp"],
                        "value_kwh": v.get("primaryValue", v.get("secondaryValue")),
                    })
                    count += 1
            print(f"    {chunk_start} to {chunk_end}: {count} readings")

    write_header = not os.path.exists(OUT_FILE)
    with open(OUT_FILE, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerows(rows)
    print(f"\nWrote {len(rows):,} rows to {OUT_FILE}")


if __name__ == "__main__":
    main()

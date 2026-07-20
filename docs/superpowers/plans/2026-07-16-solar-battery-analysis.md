# Solar + Battery Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Simulate combined solar + battery systems overlaid on real metered half-hourly consumption data, sweeping panel size (kWp) × battery size (kWh) and producing text tables and heatmap plots.

**Architecture:** Three new files — `solar_profile.py` (PVGIS API + measured sandbox profiles), `solar_battery_simulator.py` (per-day dispatch with solar priority), `solar_analysis.py` (sweep, text output, heatmaps, week plot). Plus `pull_solar_production.py` to fetch measured production data. All existing files untouched.

**Tech Stack:** Python, pandas, requests, matplotlib, n3rgy sandbox API (existing pattern), PVGIS REST API.

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `pull_solar_production.py` | Create | One-shot script: fetch production data for 3 sandbox PV MPXNs → `data/solar_production.csv` |
| `solar_battery_simulator.py` | Create | `simulate_day_solar()` — dispatch priority: solar → battery → grid |
| `solar_profile.py` | Create | `get_pvgis_profile()` + `get_measured_profile()` → `{date: list[48]}` kWh per kWp |
| `solar_analysis.py` | Create | Sweep panel×battery, produce text table + heatmaps + week plot |
| `tests/test_solar_battery_simulator.py` | Create | Unit tests for dispatch logic |
| `tests/test_solar_profile.py` | Create | Unit tests for profile generation |
| `.gitignore` | Modify | Add new data/cache files |

**Both profile functions return the same type:** `dict[date, list[48 floats]]` where values are **kWh per kWp**. The analysis multiplies by the chosen `panel_kwp` to get absolute generation.

---

## Task 1: Pull solar production data

**Files:**
- Create: `pull_solar_production.py`
- Modify: `.gitignore`

- [ ] **Step 1: Update .gitignore**

Add to `.gitignore`:
```
data/solar_production.csv
data/pvgis_cache_*.json
data/*-solar-results.txt
data/*-solar-heatmap-*.png
data/*-solar-wk*.png
```

- [ ] **Step 2: Create `pull_solar_production.py`**

```python
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
```

- [ ] **Step 3: Run the script**

```bash
python py/pull_solar_production.py
```

Expected output ends with: `Wrote N rows to data/solar_production.csv`

- [ ] **Step 4: Commit**

```bash
git add pull_solar_production.py .gitignore
git commit -m "feat: add solar production data pull script"
```

---

## Task 2: Solar battery simulator — TDD

**Files:**
- Create: `tests/test_solar_battery_simulator.py`
- Create: `solar_battery_simulator.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_solar_battery_simulator.py`:

```python
import pytest
from solar_battery_simulator import simulate_day_solar


def test_no_solar_no_battery_zero_saving():
    """No solar, no battery → cost equals baseline, saving = 0."""
    consumption = [0.5] * 48
    tariff = [8.78] * 24 + [16.29] * 24
    solar = [0.0] * 48
    result = simulate_day_solar(
        consumption, tariff, solar,
        battery_capacity_kwh=0,
        round_trip_efficiency=1.0,
        max_c_rate=0.5,
        min_soc=0.0,
        export_rate_p=0.0,
    )
    assert result["daily_saving_p"] == pytest.approx(0.0)
    assert result["solar_self_consumed_kwh"] == pytest.approx(0.0)
    assert result["solar_exported_kwh"] == pytest.approx(0.0)
    assert result["peak_kwh_displaced"] == pytest.approx(0.0)


def test_solar_self_consumption_and_export_no_battery():
    """
    Solar 1.0 kWh/slot off-peak only, consumption 0.5 kWh/slot, no battery.
    Off-peak (8.78p): self-consumed 0.5, exported 0.5
    Peak (16.29p): no solar, grid covers 0.5

    baseline  = 24*0.5*8.78 + 24*0.5*16.29 = 105.36 + 195.48 = 300.84p
    grid_cost = 0          + 24*0.5*16.29  = 195.48p
    export_rev= 24*0.5*15  = 180p
    saving    = 300.84 - 195.48 + 180 = 285.36p
    """
    consumption = [0.5] * 48
    tariff = [8.78] * 24 + [16.29] * 24
    solar = [1.0] * 24 + [0.0] * 24
    result = simulate_day_solar(
        consumption, tariff, solar,
        battery_capacity_kwh=0,
        round_trip_efficiency=1.0,
        max_c_rate=0.5,
        min_soc=0.0,
        export_rate_p=15.0,
    )
    assert result["daily_saving_p"] == pytest.approx(285.36, rel=1e-4)
    assert result["solar_self_consumed_kwh"] == pytest.approx(12.0)
    assert result["solar_exported_kwh"] == pytest.approx(12.0)
    assert result["peak_kwh_displaced"] == pytest.approx(0.0)


def test_solar_charges_battery_then_discharges_at_peak():
    """
    Off-peak (8.78p): consumption 0, solar 1.0 → charges 5kWh battery then exports rest.
    Peak (16.29p): consumption 0.5 kWh/slot, no solar → battery covers first 10 slots.

    Off-peak: 4 slots to fill battery (1.0 solar + 0.25 grid each = 1.25 total per slot)
              → battery full at soc=5.0 after slot 3
              → slots 4-23: solar exported, no grid draw (consumption=0)
    Grid cost off-peak: 4 slots × 0.25 × 8.78 = 8.78p

    Peak: battery has 5.0 kWh, draw min(1.25, soc, 0.5/1.0)=0.5 per slot × 10 slots
          → soc=0 after slot 33; slots 34-47 from grid: 14 × 0.5 × 16.29 = 114.03p

    baseline  = 24*0*8.78 + 24*0.5*16.29 = 195.48p
    grid_cost = 8.78 + 114.03 = 122.81p
    export_rev= 20 * 0 = 0 (export_rate=0)
    saving    = 195.48 - 122.81 = 72.67p
    """
    consumption = [0.0] * 24 + [0.5] * 24
    tariff = [8.78] * 24 + [16.29] * 24
    solar = [1.0] * 24 + [0.0] * 24
    result = simulate_day_solar(
        consumption, tariff, solar,
        battery_capacity_kwh=5.0,
        round_trip_efficiency=1.0,
        max_c_rate=0.5,
        min_soc=0.0,
        export_rate_p=0.0,
    )
    assert result["daily_saving_p"] == pytest.approx(72.67, rel=1e-3)
    assert result["solar_self_consumed_kwh"] == pytest.approx(0.0)
    assert result["solar_exported_kwh"] == pytest.approx(20.0)
    assert result["peak_kwh_displaced"] == pytest.approx(5.0)


def test_no_solar_battery_only_matches_battery_simulator():
    """
    With solar=0, simulate_day_solar should give the same result as battery_simulator.simulate_day.
    5kWh battery, rte=1.0, consumption=1.0, 2-rate tariff, min_soc=0.
    Charges 4 slots × 1.25 = 5 kWh off-peak. Discharges 5 slots × 1.0 at peak.
    saving = 5 * (16.29 - 8.78) = 37.55p
    """
    consumption = [1.0] * 48
    tariff = [8.78] * 24 + [16.29] * 24
    solar = [0.0] * 48
    result = simulate_day_solar(
        consumption, tariff, solar,
        battery_capacity_kwh=5.0,
        round_trip_efficiency=1.0,
        max_c_rate=0.5,
        min_soc=0.0,
        export_rate_p=0.0,
    )
    assert result["daily_saving_p"] == pytest.approx(37.55, rel=1e-3)
    assert result["peak_kwh_displaced"] == pytest.approx(5.0)
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_solar_battery_simulator.py -v
```

Expected: 4 errors — `ModuleNotFoundError: No module named 'solar_battery_simulator'`

- [ ] **Step 3: Implement `solar_battery_simulator.py`**

```python
def simulate_day_solar(
    consumption_hh,
    tariff_hh,
    solar_hh,
    battery_capacity_kwh,
    round_trip_efficiency=0.92,
    max_c_rate=0.5,
    min_soc=0.20,
    export_rate_p=15.0,
):
    """
    Simulate one day of solar + battery dispatch across 48 half-hourly slots.

    Dispatch priority per slot:
      1. Solar offsets consumption (self-consumption)
      2. Surplus solar charges battery (up to C-rate)
      3. Remaining surplus exported at export_rate_p
      4. Off-peak: grid tops up battery with remaining C-rate capacity
      5. Peak: battery discharges to cover net load (after solar offset)
      6. Grid covers any remaining net load

    Args:
        consumption_hh:       list[48] kWh consumed per half-hour
        tariff_hh:            list[48] p/kWh for each half-hour
        solar_hh:             list[48] kWh generated per half-hour
        battery_capacity_kwh: usable battery capacity in kWh
        round_trip_efficiency: fraction of charged energy delivered (default 0.92)
        max_c_rate:           max charge/discharge as fraction of capacity per hour
        min_soc:              minimum state of charge as fraction of capacity
        export_rate_p:        p/kWh received for exported solar

    Returns:
        dict with keys:
            daily_saving_p          — net saving vs no-solar no-battery baseline (pence)
            solar_self_consumed_kwh — solar directly offsetting consumption
            solar_exported_kwh      — solar sent to grid
            peak_kwh_displaced      — energy delivered from battery at peak
    """
    off_peak_rate = min(tariff_hh)
    peak_rate = max(tariff_hh)
    max_hh_kwh = battery_capacity_kwh * max_c_rate * 0.5
    min_energy = battery_capacity_kwh * min_soc

    soc = min_energy
    baseline_cost_p = sum(c * r for c, r in zip(consumption_hh, tariff_hh))
    grid_cost_p = 0.0
    export_revenue_p = 0.0
    total_self_consumed = 0.0
    total_exported = 0.0
    total_peak_displaced = 0.0

    for i in range(48):
        rate = tariff_hh[i]
        solar = solar_hh[i]
        consumption = consumption_hh[i]

        # 1. Solar self-consumption
        self_consumed = min(solar, consumption)
        surplus_solar = solar - self_consumed
        net_load = consumption - self_consumed
        total_self_consumed += self_consumed

        # 2. Surplus solar charges battery
        charge_from_solar = 0.0
        if surplus_solar > 0 and battery_capacity_kwh > 0:
            space = battery_capacity_kwh - soc
            charge_from_solar = min(max_hh_kwh, space, surplus_solar)
            soc += charge_from_solar
            surplus_solar -= charge_from_solar

        # 3. Remaining surplus exported
        total_exported += surplus_solar
        export_revenue_p += surplus_solar * export_rate_p

        # 4 & 5: off-peak grid charges OR peak battery discharges (mutually exclusive)
        if rate <= off_peak_rate and battery_capacity_kwh > 0:
            remaining_c_rate = max_hh_kwh - charge_from_solar
            space = battery_capacity_kwh - soc
            charge_from_grid = min(remaining_c_rate, space)
            soc += charge_from_grid
            net_load += charge_from_grid
        elif rate >= peak_rate and battery_capacity_kwh > 0 and net_load > 0:
            available = soc - min_energy
            draw = min(max_hh_kwh, available, net_load / round_trip_efficiency)
            draw = max(0.0, draw)
            soc -= draw
            delivered = draw * round_trip_efficiency
            net_load -= delivered
            total_peak_displaced += delivered

        # 6. Grid covers remaining net load
        grid_cost_p += max(0.0, net_load) * rate

    saving_p = baseline_cost_p - grid_cost_p + export_revenue_p

    return {
        "daily_saving_p": saving_p,
        "solar_self_consumed_kwh": total_self_consumed,
        "solar_exported_kwh": total_exported,
        "peak_kwh_displaced": total_peak_displaced,
    }
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
pytest tests/test_solar_battery_simulator.py -v
```

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add solar_battery_simulator.py tests/test_solar_battery_simulator.py
git commit -m "feat: add solar+battery day simulator with TDD"
```

---

## Task 3: Solar profile — PVGIS

**Files:**
- Create: `tests/test_solar_profile.py`
- Create: `solar_profile.py` (partial — PVGIS function only)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_solar_profile.py`:

```python
import json
import os
import pytest
from datetime import date
from unittest.mock import patch, MagicMock
from solar_profile import get_pvgis_profile


def _make_pvgis_response(slots_with_watts):
    """Build a minimal PVGIS hourly response. slots_with_watts: {(month, day, hour): watts}"""
    hourly = []
    for (month, day, hour), watts in slots_with_watts.items():
        hourly.append({"time": f"2023{month:02d}{day:02d}:{hour:02d}10", "P": watts})
    return {"outputs": {"hourly": hourly}}


def test_pvgis_profile_converts_watts_to_halfhourly_kwh_per_kwp(tmp_path):
    """
    PVGIS returns hourly P in Watts for 1 kWp.
    500W at noon on June 1 → 500/1000/2 = 0.25 kWh per half-hourly slot per kWp.
    Both slot 24 (12:00) and slot 25 (12:30) should be 0.25.
    Nighttime (hour 0) should be 0.0.
    """
    mock_data = _make_pvgis_response({
        (6, 1, 0): 0.0,
        (6, 1, 12): 500.0,
        (6, 1, 13): 400.0,
    })
    with patch("solar_profile.requests.get") as mock_get:
        mock_get.return_value.json.return_value = mock_data
        mock_get.return_value.raise_for_status = MagicMock()
        profile = get_pvgis_profile(lat=51.5, lon=-0.1, tilt=35, azimuth=180,
                                    year=2023, cache_dir=str(tmp_path))

    assert date(2023, 6, 1) in profile
    slots = profile[date(2023, 6, 1)]
    assert len(slots) == 48
    assert slots[0] == pytest.approx(0.0)    # midnight
    assert slots[1] == pytest.approx(0.0)    # 00:30
    assert slots[24] == pytest.approx(0.25)  # 12:00
    assert slots[25] == pytest.approx(0.25)  # 12:30
    assert slots[26] == pytest.approx(0.20)  # 13:00 (400W)
    assert slots[27] == pytest.approx(0.20)  # 13:30


def test_pvgis_profile_caches_and_avoids_second_api_call(tmp_path):
    """Second call with same lat/lon/year must use cache, not hit the API again."""
    mock_data = _make_pvgis_response({(6, 1, 12): 300.0})
    with patch("solar_profile.requests.get") as mock_get:
        mock_get.return_value.json.return_value = mock_data
        mock_get.return_value.raise_for_status = MagicMock()
        get_pvgis_profile(lat=51.5, lon=-0.1, cache_dir=str(tmp_path))
        get_pvgis_profile(lat=51.5, lon=-0.1, cache_dir=str(tmp_path))
        assert mock_get.call_count == 1
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_solar_profile.py -v
```

Expected: 2 errors — `ModuleNotFoundError: No module named 'solar_profile'`

- [ ] **Step 3: Implement `get_pvgis_profile` in `solar_profile.py`**

```python
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
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
pytest tests/test_solar_profile.py -v
```

Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add solar_profile.py tests/test_solar_profile.py
git commit -m "feat: add PVGIS solar profile with caching"
```

---

## Task 4: Solar profile — measured

**Files:**
- Modify: `tests/test_solar_profile.py` (add 2 tests)
- Modify: `solar_profile.py` (add `get_measured_profile`)

- [ ] **Step 1: Add failing tests to `tests/test_solar_profile.py`**

Append to `tests/test_solar_profile.py`:

```python
import pandas as pd
from solar_profile import get_measured_profile


def test_measured_profile_raises_if_csv_missing(tmp_path):
    with pytest.raises(FileNotFoundError, match="pull_solar_production.py"):
        get_measured_profile(str(tmp_path))


def test_measured_profile_structure_and_normalisation(tmp_path):
    """
    Profile must:
    - Return dict keyed by date(2023, ...) with list[48] values
    - Have 0.0 at midnight (slot 0)
    - Annual total ≈ 900 kWh/kWp when scaled by days in each month
    """
    # Build synthetic data: uniform 1.0 kWh/slot during hours 8-17 for all days in 2023
    rows = []
    for mpxn in ["2234567891000", "5330642497188"]:
        d = date(2023, 1, 1)
        while d <= date(2023, 12, 31):
            for hour in range(24):
                for minute in [0, 30]:
                    val = 1.0 if 8 <= hour <= 17 else 0.0
                    rows.append({
                        "mpxn": mpxn,
                        "timestamp": f"{d} {hour:02d}:{minute:02d}",
                        "value_kwh": val,
                    })
            d += timedelta(days=1)

    pd.DataFrame(rows).to_csv(str(tmp_path / "solar_production.csv"), index=False)

    profile = get_measured_profile(str(tmp_path))

    assert all(d.year == 2023 for d in profile)
    assert date(2023, 6, 15) in profile
    assert len(profile[date(2023, 6, 15)]) == 48
    assert profile[date(2023, 6, 15)][0] == pytest.approx(0.0)   # midnight
    assert profile[date(2023, 6, 15)][16] > 0                     # 8am slot has generation

    days_in_month = {1:31, 2:28, 3:31, 4:30, 5:31, 6:30, 7:31, 8:31, 9:30, 10:31, 11:30, 12:31}
    annual = sum(
        sum(profile[date(2023, m, 1)]) * days_in_month[m]
        for m in range(1, 13)
    )
    assert annual == pytest.approx(900.0, rel=0.05)
```

- [ ] **Step 2: Run new tests to confirm they fail**

```bash
pytest tests/test_solar_profile.py::test_measured_profile_raises_if_csv_missing tests/test_solar_profile.py::test_measured_profile_structure_and_normalisation -v
```

Expected: 2 errors — `ImportError: cannot import name 'get_measured_profile'`

- [ ] **Step 3: Add `get_measured_profile` to `solar_profile.py`**

Append to `solar_profile.py`:

```python
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

    # Build profile: {date(2023, m, d): list[48]} in kWh per kWp
    profile = {}
    d = date(2023, 1, 1)
    while d <= date(2023, 12, 31):
        profile[d] = [shape_dict.get((d.month, s), 0.0) * scale for s in range(48)]
        d += timedelta(days=1)

    return profile
```

- [ ] **Step 4: Run all solar profile tests**

```bash
pytest tests/test_solar_profile.py -v
```

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add solar_profile.py tests/test_solar_profile.py
git commit -m "feat: add measured solar profile from sandbox PV data"
```

---

## Task 5: Solar analysis — data loading, sweep, and text tables

**Files:**
- Create: `solar_analysis.py`

This is the largest task. Build `solar_analysis.py` in full — configuration, data loading (copied verbatim from `battery_analysis.py`), the two-profile sweep, and text table output.

- [ ] **Step 1: Create `solar_analysis.py`**

```python
import os
from datetime import date

import numpy as np
import pandas as pd

from solar_battery_simulator import simulate_day_solar
from solar_profile import get_pvgis_profile, get_measured_profile

# ── Meter configuration ───────────────────────────────────────────────────────
MPAN         = "1234567891024"
METER_NUMBER = 5
LAT          = 53.60    # WF9 2UW — South Elmsall
LON          = -1.32

# ── System parameters ─────────────────────────────────────────────────────────
PANEL_SIZES_KWP      = [2, 4, 6, 8, 10, 12]
BATTERY_SIZES_KWH    = [0, 2, 5, 7, 10, 13, 15]
SOLAR_COST_PER_KWP   = 900      # GBP/kWp
BATTERY_COST_PER_KWH = 500      # GBP/kWh
EXPORT_RATE_P        = 15.0     # p/kWh Smart Export Guarantee
PANEL_TILT           = 35
PANEL_AZIMUTH        = 180
WARRANTY_YEARS       = 15
MIN_SOC              = 0.20
BATTERY_CONFIGS = [
    {"label": "0.5C", "max_c_rate": 0.5, "rte": 0.92},
    {"label": "1C",   "max_c_rate": 1.0, "rte": 0.88},
]

DATA_DIR    = "data"
OUTPUT_FILE = f"data/m{METER_NUMBER}-solar-results.txt"
WEEK_START  = pd.Timestamp("2026-07-06")
WEEK_END    = pd.Timestamp("2026-07-12")
PLOT_PANEL_KWP   = 6
PLOT_BATTERY_KWH = 5


def load_data():
    consumption = pd.read_csv(f"{DATA_DIR}/consumption.csv")
    consumption = consumption[
        (consumption["mpxn"] == int(MPAN)) & (consumption["utility"] == "electricity")
    ][["timestamp", "value"]].copy()
    consumption["timestamp"] = pd.to_datetime(consumption["timestamp"])
    consumption = consumption.rename(columns={"value": "consumption_kwh"})
    consumption = consumption.drop_duplicates(subset="timestamp", keep="first")

    tariff_raw = pd.read_csv(f"{DATA_DIR}/tariff.csv")
    tariff_raw = tariff_raw[
        (tariff_raw["mpan"] == int(MPAN))
        & (tariff_raw["energy_type"] == "electricity")
        & (tariff_raw["type"] == "unit_rate")
    ][["timestamp", "value"]].copy()
    tariff_raw["timestamp"] = pd.to_datetime(tariff_raw["timestamp"])
    tariff_raw["time_of_day"] = tariff_raw["timestamp"].dt.time
    tod_rate = tariff_raw.groupby("time_of_day")["value"].first().to_dict()

    consumption["time_of_day"] = consumption["timestamp"].dt.time
    consumption["rate_p"] = consumption["time_of_day"].map(tod_rate)
    merged = consumption.dropna(subset=["rate_p"]).drop(columns=["time_of_day"])
    merged["date"] = merged["timestamp"].dt.date
    return merged


def build_daily_arrays(merged):
    days = []
    for d, group in merged.groupby("date"):
        group = group.sort_values("timestamp")
        if len(group) != 48:
            continue
        days.append((d, group["consumption_kwh"].tolist(), group["rate_p"].tolist()))
    return days


def to_profile_date(d):
    """Map any simulation date to its 2023 equivalent for solar profile lookup."""
    if d.month == 2 and d.day == 29:
        return date(2023, 2, 28)
    return date(2023, d.month, d.day)


def run_sweep(days, solar_profile, config):
    """
    Sweep all panel × battery combinations.
    Returns (savings_gbp, paybacks) as 2D numpy arrays shaped
    (len(PANEL_SIZES_KWP), len(BATTERY_SIZES_KWH)).
    """
    rte = config["rte"]
    max_c_rate = config["max_c_rate"]
    n_panels = len(PANEL_SIZES_KWP)
    n_batts = len(BATTERY_SIZES_KWH)
    savings = np.zeros((n_panels, n_batts))
    paybacks = np.full((n_panels, n_batts), np.inf)

    for pi, panel_kwp in enumerate(PANEL_SIZES_KWP):
        # Pre-scale solar profile for this panel size
        solar_per_day = {
            d: [v * panel_kwp for v in solar_profile.get(to_profile_date(d), [0.0] * 48)]
            for d, _, _ in days
        }
        for bi, battery_kwh in enumerate(BATTERY_SIZES_KWH):
            results = [
                simulate_day_solar(
                    c, t, solar_per_day[d],
                    battery_kwh, rte, max_c_rate, MIN_SOC, EXPORT_RATE_P,
                )
                for d, c, t in days
            ]
            avg_daily_p = sum(r["daily_saving_p"] for r in results) / len(days)
            annual_gbp = avg_daily_p * 365 / 100
            installed = panel_kwp * SOLAR_COST_PER_KWP + battery_kwh * BATTERY_COST_PER_KWH
            paybacks[pi][bi] = installed / annual_gbp if annual_gbp > 0 else np.inf
            savings[pi][bi] = annual_gbp

    return savings, paybacks


def build_text_table(days, savings, paybacks, profile_label, config):
    col_w = 16
    header = f"{'Panel':>8} | " + " | ".join(
        f"{b:>3} kWh".center(col_w) for b in BATTERY_SIZES_KWH
    )
    divider = "-" * 8 + "-+-" + ("-" * col_w + "-+-") * len(BATTERY_SIZES_KWH)

    lines = [
        f"-- {profile_label} Profile | {config['label']} Battery --",
        header,
        divider,
    ]
    for pi, panel_kwp in enumerate(PANEL_SIZES_KWP):
        cells = []
        for bi in range(len(BATTERY_SIZES_KWH)):
            s = savings[pi][bi]
            p = paybacks[pi][bi]
            flag = "*" if p > WARRANTY_YEARS else " "
            cells.append(f"£{s:>5,.0f}/yr {p:>4.1f}y{flag}".center(col_w))
        lines.append(f"{panel_kwp:>5} kWp | " + " | ".join(cells))

    lines.append(divider)
    if any(paybacks[pi][bi] > WARRANTY_YEARS
           for pi in range(len(PANEL_SIZES_KWP))
           for bi in range(len(BATTERY_SIZES_KWH))):
        lines.append(f"* Payback exceeds {WARRANTY_YEARS}-year warranty period.")
    return lines


def main():
    print("Loading data...")
    merged = load_data()
    days = build_daily_arrays(merged)
    date_min = min(d for d, _, _ in days)
    date_max = max(d for d, _, _ in days)
    off_peak = min(merged["rate_p"])
    peak = max(merged["rate_p"])

    # Baseline: no solar, no battery
    baseline_daily_cost_p = sum(
        sum(c[i] * t[i] for i in range(48)) for _, c, t in days
    ) / len(days)
    baseline_annual_gbp = baseline_daily_cost_p * 365 / 100

    print("Fetching PVGIS profile...")
    pvgis_profile = get_pvgis_profile(LAT, LON, PANEL_TILT, PANEL_AZIMUTH,
                                      year=2023, cache_dir=DATA_DIR)

    print("Building measured profile...")
    measured_profile = get_measured_profile(DATA_DIR)

    profiles = [("PVGIS", pvgis_profile), ("Measured", measured_profile)]

    lines = [
        f"Solar + Battery Analysis - MPAN {MPAN}",
        f"Tariff: {off_peak}p off-peak / {peak}p peak  |  "
        f"Solar: £{SOLAR_COST_PER_KWP}/kWp  |  Battery: £{BATTERY_COST_PER_KWH}/kWh  |  "
        f"Export: {EXPORT_RATE_P}p/kWh SEG",
        f"Days simulated: {len(days):,} ({date_min} to {date_max})  |  Min SOC: {MIN_SOC*100:.0f}%",
        f"Baseline (no solar, no battery): £{baseline_annual_gbp:,.2f}/yr",
        "",
    ]

    all_results = {}  # (profile_label, config_label) → (savings, paybacks)

    for profile_label, solar_profile in profiles:
        for config in BATTERY_CONFIGS:
            print(f"Sweeping {profile_label} / {config['label']}...")
            savings, paybacks = run_sweep(days, solar_profile, config)
            all_results[(profile_label, config["label"])] = (savings, paybacks)
            lines.extend(build_text_table(days, savings, paybacks, profile_label, config))
            lines.append("")

    output = "\n".join(lines)
    print(output)
    with open(OUTPUT_FILE, "w") as f:
        f.write(output + "\n")
    print(f"\nResults saved to {OUTPUT_FILE}")

    return days, merged, all_results, profiles


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run to verify text output**

```bash
python py/solar_analysis.py
```

Expected: sweeps all combinations, prints tables, saves `data/m5-solar-results.txt`. Takes 2–5 minutes.

- [ ] **Step 3: Commit**

```bash
git add solar_analysis.py
git commit -m "feat: solar analysis core — sweep + text tables"
```

---

## Task 6: Solar analysis — heatmap plots

**Files:**
- Modify: `solar_analysis.py` (add `plot_heatmap` function and call from `main`)

- [ ] **Step 1: Add `plot_heatmap` function**

Add this function to `solar_analysis.py` before `main()`:

```python
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.colors as mcolors


def plot_heatmap(savings, paybacks, profile_label, config_label):
    n_panels = len(PANEL_SIZES_KWP)
    n_batts = len(BATTERY_SIZES_KWH)
    data = np.clip(paybacks, 0, 20)

    fig, ax = plt.subplots(figsize=(13, 7))
    cmap = plt.cm.RdYlGn_r
    im = ax.imshow(data, cmap=cmap, vmin=0, vmax=20, aspect="auto")
    plt.colorbar(im, ax=ax, label="Payback period (years)")

    # Contour at 10 years
    if data.min() < 10 < data.max():
        ax.contour(data, levels=[10], colors=["#032147"], linewidths=[1.5])

    # Cell annotations
    for pi in range(n_panels):
        for bi in range(n_batts):
            p = paybacks[pi][bi]
            s = savings[pi][bi]
            text = f"{p:.1f}yr\n£{s:.0f}/yr" if p < np.inf else f">20yr\n£{s:.0f}/yr"
            color = "white" if p > 15 or p < 4 else "black"
            ax.text(bi, pi, text, ha="center", va="center", fontsize=8.5, color=color)
            if p > WARRANTY_YEARS:
                ax.add_patch(mpatches.Rectangle(
                    (bi - 0.5, pi - 0.5), 1, 1,
                    fill=False, hatch="////", edgecolor="gray", linewidth=0,
                ))

    ax.set_xticks(range(n_batts))
    ax.set_xticklabels([f"{b} kWh" for b in BATTERY_SIZES_KWH])
    ax.set_yticks(range(n_panels))
    ax.set_yticklabels([f"{p} kWp" for p in PANEL_SIZES_KWP])
    ax.set_xlabel("Battery size (kWh)", fontsize=11)
    ax.set_ylabel("Panel size (kWp)", fontsize=11)
    ax.set_title(
        f"Meter {METER_NUMBER} (MPAN {MPAN}) — Solar + Battery Payback\n"
        f"{profile_label} profile | {config_label} battery | "
        f"Export {EXPORT_RATE_P}p/kWh | Solar £{SOLAR_COST_PER_KWP}/kWp | "
        f"Battery £{BATTERY_COST_PER_KWH}/kWh",
        fontsize=11,
    )
    plt.tight_layout()
    out = f"{DATA_DIR}/m{METER_NUMBER}-solar-heatmap-{profile_label.lower()}-{config_label}.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Heatmap saved to {out}")
```

- [ ] **Step 2: Call `plot_heatmap` from `main()`**

In `main()`, after the text output lines and before `return`, add:

```python
    print("Generating heatmaps...")
    for profile_label, _ in profiles:
        for config in BATTERY_CONFIGS:
            savings, paybacks = all_results[(profile_label, config["label"])]
            plot_heatmap(savings, paybacks, profile_label, config["label"])
```

- [ ] **Step 3: Run to verify heatmaps are saved**

```bash
python py/solar_analysis.py 2>&1 | grep -E "saved|Error"
```

Expected: 4 lines like `Heatmap saved to data/m5-solar-heatmap-pvgis-0.5C.png`

- [ ] **Step 4: Commit**

```bash
git add solar_analysis.py
git commit -m "feat: add solar+battery payback heatmaps"
```

---

## Task 7: Solar analysis — week plot

**Files:**
- Modify: `solar_analysis.py` (add `simulate_week_solar` and `plot_solar_week` functions)

- [ ] **Step 1: Add week simulation and plot functions**

Add these two functions to `solar_analysis.py` before `main()`:

```python
import matplotlib.dates as mdates
import numpy as np


def simulate_week_solar(week_df, solar_profile, panel_kwp, battery_kwh, config):
    rte = config["rte"]
    max_c_rate = config["max_c_rate"]
    max_hh = battery_kwh * max_c_rate * 0.5
    min_e = battery_kwh * MIN_SOC
    soc = min_e

    solar_list, self_consumed_list, exported_list = [], [], []
    charge_list, discharge_list, soc_list = [], [], []

    for d, group in week_df.groupby(week_df["timestamp"].dt.date):
        group = group.sort_values("timestamp")
        cons = group["consumption_kwh"].tolist()
        rates = group["rate_p"].tolist()
        solar_hh = [v * panel_kwp for v in solar_profile.get(to_profile_date(d), [0.0] * 48)]
        off_peak = min(rates)
        peak = max(rates)

        for i in range(48):
            rate = rates[i]
            solar = solar_hh[i]
            consumption = cons[i]

            self_c = min(solar, consumption)
            surplus = solar - self_c
            net_load = consumption - self_c

            charge_solar = 0.0
            if surplus > 0 and battery_kwh > 0:
                space = battery_kwh - soc
                charge_solar = min(max_hh, space, surplus)
                soc += charge_solar
                surplus -= charge_solar

            exported = surplus

            charge_grid = 0.0
            discharge = 0.0
            if rate <= off_peak and battery_kwh > 0:
                remaining = max_hh - charge_solar
                space = battery_kwh - soc
                charge_grid = min(remaining, space)
                soc += charge_grid
                net_load += charge_grid
            elif rate >= peak and battery_kwh > 0 and net_load > 0:
                available = soc - min_e
                draw = min(max_hh, available, net_load / rte)
                draw = max(0.0, draw)
                soc -= draw
                discharge = draw * rte
                net_load -= discharge

            solar_list.append(solar)
            self_consumed_list.append(self_c)
            exported_list.append(exported)
            charge_list.append(charge_solar + charge_grid)
            discharge_list.append(discharge)
            soc_list.append(soc)

    return (
        np.array(solar_list),
        np.array(self_consumed_list),
        np.array(exported_list),
        np.array(charge_list),
        np.array(discharge_list),
        np.array(soc_list),
    )


def plot_solar_week(merged, solar_profile, panel_kwp, battery_kwh, config):
    full_index = pd.date_range(
        WEEK_START, WEEK_END + pd.Timedelta(hours=23, minutes=30), freq="30min"
    )
    week = pd.DataFrame({"timestamp": full_index})
    week = week.merge(
        merged[["timestamp", "consumption_kwh", "rate_p"]], on="timestamp", how="left"
    )
    week["consumption_kwh"] = week["consumption_kwh"].fillna(0.0)
    week["rate_p"] = week["rate_p"].fillna(method="ffill")

    solar, self_c, exported, charge, discharge, soc = simulate_week_solar(
        week, solar_profile, panel_kwp, battery_kwh, config
    )

    ts = week["timestamp"].values
    consumption = week["consumption_kwh"].values
    tariff = week["rate_p"].values
    net_grid = consumption + charge - discharge

    week_num = WEEK_START.isocalendar()[1]
    fig, axes = plt.subplots(4, 1, figsize=(16, 13), sharex=True,
                             gridspec_kw={"height_ratios": [2, 2, 1, 1]})
    fig.suptitle(
        f"Meter {METER_NUMBER} (MPAN {MPAN}) — Week {week_num} "
        f"({WEEK_START.strftime('%d %b')}–{WEEK_END.strftime('%d %b %Y')})  |  "
        f"{panel_kwp} kWp Solar + {battery_kwh} kWh Battery ({config['label']})",
        fontsize=13, fontweight="bold",
    )

    # Panel 0: solar generation
    ax = axes[0]
    ax.fill_between(ts, 0, solar, step="post", color="#ecad0a", alpha=0.6, label="Solar generation")
    ax.step(ts, solar, where="post", color="#ecad0a", linewidth=1)
    ax.fill_between(ts, 0, self_c, step="post", color="#209dd7", alpha=0.4, label="Self-consumed")
    ax.set_ylabel("Energy (kWh / hh)", fontsize=10)
    ax.set_title("Solar Generation", fontsize=10, loc="left")
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(True, alpha=0.25)
    ax.set_ylim(bottom=0)

    # Panel 1: consumption vs net grid
    ax = axes[1]
    ax.step(ts, consumption, where="post", color="#209dd7", linewidth=1.5,
            label="Consumption", zorder=3)
    ax.step(ts, net_grid, where="post", color="#753991", linewidth=1.5,
            label="Net grid draw", zorder=3)
    ax.fill_between(ts, consumption, net_grid,
                    where=(net_grid > consumption), step="post",
                    color="#ecad0a", alpha=0.4, label="Grid charging battery")
    ax.fill_between(ts, consumption, net_grid,
                    where=(net_grid < consumption), step="post",
                    color="#032147", alpha=0.4, label="Solar/battery saving")
    ax.set_ylabel("Energy (kWh / hh)", fontsize=10)
    ax.set_title("Consumption vs Net Grid Draw", fontsize=10, loc="left")
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(True, alpha=0.25)
    ax.set_ylim(bottom=-0.05)

    # Panel 2: battery SOC
    ax = axes[2]
    ax.fill_between(ts, 0, soc, step="post", color="#032147", alpha=0.5)
    ax.step(ts, soc, where="post", color="#032147", linewidth=1)
    ax.axhline(battery_kwh * MIN_SOC, color="red", linestyle="--", linewidth=0.8, alpha=0.7,
               label=f"Min SOC ({battery_kwh * MIN_SOC:.1f} kWh)")
    ax.axhline(battery_kwh, color="#888888", linestyle=":", linewidth=0.8, alpha=0.7,
               label=f"Full ({battery_kwh} kWh)")
    ax.set_ylabel("SOC (kWh)", fontsize=10)
    ax.set_ylim(0, battery_kwh * 1.1)
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(True, alpha=0.25)

    # Panel 3: tariff
    ax = axes[3]
    ax.step(ts, tariff, where="post", color="red", linewidth=1)
    ax.fill_between(ts, 0, tariff, step="post", color="red", alpha=0.2)
    ax.set_ylabel("Tariff (p/kWh)", fontsize=10)
    ax.grid(True, alpha=0.25)
    ax.xaxis.set_major_locator(mdates.DayLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%a\n%d %b"))

    plt.tight_layout()
    out = f"{DATA_DIR}/m{METER_NUMBER}-solar-wk{week_num}.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Week plot saved to {out}")
```

- [ ] **Step 2: Call `plot_solar_week` from `main()`**

At the end of `main()`, before `return`, add:

```python
    print("Generating week plot...")
    plot_config = BATTERY_CONFIGS[0]  # 0.5C
    plot_solar_week(merged, pvgis_profile, PLOT_PANEL_KWP, PLOT_BATTERY_KWH, plot_config)
```

- [ ] **Step 3: Run to verify week plot is saved**

```bash
python py/solar_analysis.py 2>&1 | grep -E "Week plot|Error"
```

Expected: `Week plot saved to data/m5-solar-wk27.png`

- [ ] **Step 4: Commit**

```bash
git add solar_analysis.py
git commit -m "feat: add solar+battery week visualisation plot"
```

---

## Task 8: Run full analysis and commit all outputs

- [ ] **Step 1: Run all existing tests to confirm nothing is broken**

```bash
pytest -v
```

Expected: all tests pass (battery_simulator tests + solar tests)

- [ ] **Step 2: Run the full solar analysis**

```bash
python py/solar_analysis.py
```

Expected: prints sweep progress for 4 profile×config combinations, saves:
- `data/m5-solar-results.txt`
- `data/m5-solar-heatmap-pvgis-0.5C.png`
- `data/m5-solar-heatmap-pvgis-1C.png`
- `data/m5-solar-heatmap-measured-0.5C.png`
- `data/m5-solar-heatmap-measured-1C.png`
- `data/m5-solar-wk27.png`

- [ ] **Step 3: Commit**

```bash
git add pull_solar_production.py solar_profile.py solar_battery_simulator.py solar_analysis.py tests/test_solar_battery_simulator.py tests/test_solar_profile.py .gitignore
git commit -m "feat: complete solar+battery analysis with PVGIS and measured profiles"
```

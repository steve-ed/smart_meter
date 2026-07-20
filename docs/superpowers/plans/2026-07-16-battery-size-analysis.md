# Battery Size Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python script that prints a payback table for home battery sizes 2–15 kWh using real half-hourly consumption and tariff data for MPAN 1234567891000.

**Architecture:** A pure simulation module (`battery_simulator.py`) contains `simulate_day()` with no I/O, keeping it testable. An entry-point script (`battery_analysis.py`) loads data from `data/`, runs the simulation across 273 overlapping days (2024-01-01 to 2026-04-01), and prints the results table. This mirrors the existing `anomaly_detector.py` pattern.

**Tech Stack:** Python 3, pandas (already used throughout project), csv stdlib for data loading.

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `battery_simulator.py` | Create | Pure `simulate_day()` function — no I/O |
| `battery_analysis.py` | Create | Data loading, simulation loop, table output |
| `tests/test_battery_simulator.py` | Create | Unit tests for `simulate_day()` |

---

## Background: Data

- **Tariff** (`data/tariff.csv`): MPAN 1234567891000 has a 2-rate time-of-use tariff: `8.78p/kWh` (off-peak: 00:00–06:30 and 23:00–23:30) and `16.29p/kWh` (peak: 07:00–22:30). Covers 2012-01-01 to 2026-04-01.
- **Consumption** (`data/consumption.csv`): MPXN 1234567891000, electricity, 2024-01-01 to 2026-07-14. Has duplicate timestamps (completeness >100%); deduplicate before use.
- **Overlap**: 273 days where both datasets exist (2024-01-01 to 2026-04-01).

---

## Task 1: Write failing tests for `simulate_day`

**Files:**
- Create: `tests/test_battery_simulator.py`

- [ ] **Step 1: Write the test file**

```python
import pytest
from battery_simulator import simulate_day


def test_no_saving_when_no_peak_slots():
    """Single rate means no arbitrage opportunity — saving is zero."""
    consumption_hh = [0.5] * 48
    tariff_hh = [8.78] * 48
    result = simulate_day(consumption_hh, tariff_hh, battery_capacity_kwh=5.0,
                          round_trip_efficiency=1.0, max_c_rate=0.5, min_soc=0.0)
    assert result["daily_saving_p"] == pytest.approx(0.0)
    assert result["peak_kwh_displaced"] == pytest.approx(0.0)


def test_battery_charges_and_saves_during_peak():
    """
    5 kWh battery, efficiency=1, min_soc=0.
    24 off-peak then 24 peak slots, consumption 1.0 kWh/slot.
    max per slot = 5 * 0.5 * 0.5 = 1.25 kWh.
    Charges to full in 4 off-peak slots (4 * 1.25 = 5.0 kWh).
    Discharges 1.0 kWh/slot for 5 peak slots until empty.
    Total delivered = 5.0 kWh.
    Saving = 5.0 * (16.29 - 8.78 / 1.0) = 5.0 * 7.51 = 37.55p.
    """
    consumption_hh = [1.0] * 48
    tariff_hh = [8.78] * 24 + [16.29] * 24
    result = simulate_day(consumption_hh, tariff_hh, battery_capacity_kwh=5.0,
                          round_trip_efficiency=1.0, max_c_rate=0.5, min_soc=0.0)
    assert result["daily_saving_p"] == pytest.approx(37.55, rel=1e-3)
    assert result["peak_kwh_displaced"] == pytest.approx(5.0, rel=1e-3)


def test_small_battery_partial_displacement():
    """
    2 kWh battery, efficiency=1, min_soc=0.
    max per slot = 2 * 0.5 * 0.5 = 0.5 kWh.
    Charges to full in 4 off-peak slots (4 * 0.5 = 2.0 kWh).
    Discharges 0.5 kWh/slot for 4 peak slots.
    Total delivered = 2.0 kWh.
    Saving = 2.0 * 7.51 = 15.02p.
    """
    consumption_hh = [1.0] * 48
    tariff_hh = [8.78] * 24 + [16.29] * 24
    result = simulate_day(consumption_hh, tariff_hh, battery_capacity_kwh=2.0,
                          round_trip_efficiency=1.0, max_c_rate=0.5, min_soc=0.0)
    assert result["daily_saving_p"] == pytest.approx(15.02, rel=1e-3)
    assert result["peak_kwh_displaced"] == pytest.approx(2.0, rel=1e-3)


def test_large_battery_capped_by_consumption():
    """
    20 kWh battery, efficiency=1, min_soc=0, consumption only 0.1 kWh/slot.
    max per slot = 20 * 0.5 * 0.5 = 5.0 kWh >> consumption.
    Battery easily fills; during peak discharges exactly 0.1 kWh/slot.
    Total delivered = 24 * 0.1 = 2.4 kWh.
    Saving = 2.4 * 7.51 = 18.024p.
    """
    consumption_hh = [0.1] * 48
    tariff_hh = [8.78] * 24 + [16.29] * 24
    result = simulate_day(consumption_hh, tariff_hh, battery_capacity_kwh=20.0,
                          round_trip_efficiency=1.0, max_c_rate=0.5, min_soc=0.0)
    assert result["daily_saving_p"] == pytest.approx(18.024, rel=1e-3)
    assert result["peak_kwh_displaced"] == pytest.approx(2.4, rel=1e-3)
```

- [ ] **Step 2: Run tests to confirm they fail**

```
cd C:\Users\steve\projects\smart_meter
pytest tests/test_battery_simulator.py -v
```

Expected: 4 errors — `ModuleNotFoundError: No module named 'battery_simulator'`

---

## Task 2: Implement `battery_simulator.py`

**Files:**
- Create: `battery_simulator.py`

- [ ] **Step 1: Write the module**

```python
def simulate_day(consumption_hh, tariff_hh, battery_capacity_kwh,
                 round_trip_efficiency=0.90, max_c_rate=0.5, min_soc=0.20):
    """
    Simulate one day of battery arbitrage across 48 half-hourly slots.

    Charges at the lowest rate in tariff_hh; discharges at the highest.
    Saving formula accounts for round-trip losses:
        saving_p = delivered * (peak_rate - off_peak_rate / efficiency)

    Args:
        consumption_hh: list of 48 floats, kWh consumed per half-hour
        tariff_hh:      list of 48 floats, p/kWh for each half-hour
        battery_capacity_kwh: usable capacity in kWh
        round_trip_efficiency: fraction of charged energy delivered (default 0.90)
        max_c_rate:     max charge/discharge as fraction of capacity per hour (default 0.5)
        min_soc:        minimum state of charge as fraction of capacity (default 0.20)

    Returns:
        dict with keys:
            daily_saving_p      — net saving in pence
            charge_cycled_kwh   — total energy put into battery
            peak_kwh_displaced  — total energy delivered to home from battery
    """
    off_peak_rate = min(tariff_hh)
    peak_rate = max(tariff_hh)
    max_hh_kwh = battery_capacity_kwh * max_c_rate * 0.5
    min_energy = battery_capacity_kwh * min_soc

    soc = min_energy
    total_delivered = 0.0
    charge_cycled = 0.0

    for i in range(48):
        rate = tariff_hh[i]
        if rate <= off_peak_rate:
            space = battery_capacity_kwh - soc
            charge = min(max_hh_kwh, space)
            soc += charge
            charge_cycled += charge
        elif rate >= peak_rate:
            available = soc - min_energy
            # draw enough from battery to deliver consumption_hh[i] kWh to home,
            # accounting for round-trip losses; cap at C-rate and available energy
            draw = min(max_hh_kwh, available,
                       consumption_hh[i] / round_trip_efficiency)
            draw = max(0.0, draw)
            soc -= draw
            total_delivered += draw * round_trip_efficiency

    # Net saving: avoided peak cost minus extra off-peak charging cost (per kWh delivered)
    saving_p = total_delivered * (peak_rate - off_peak_rate / round_trip_efficiency)

    return {
        "daily_saving_p": saving_p,
        "charge_cycled_kwh": charge_cycled,
        "peak_kwh_displaced": total_delivered,
    }
```

- [ ] **Step 2: Run tests to confirm they pass**

```
pytest tests/test_battery_simulator.py -v
```

Expected:
```
PASSED tests/test_battery_simulator.py::test_no_saving_when_no_peak_slots
PASSED tests/test_battery_simulator.py::test_battery_charges_and_saves_during_peak
PASSED tests/test_battery_simulator.py::test_small_battery_partial_displacement
PASSED tests/test_battery_simulator.py::test_large_battery_capped_by_consumption
```

- [ ] **Step 3: Commit**

```
git add battery_simulator.py tests/test_battery_simulator.py
git commit -m "feat: add battery simulator with unit tests"
```

---

## Task 3: Implement `battery_analysis.py`

**Files:**
- Create: `battery_analysis.py`

- [ ] **Step 1: Write the script**

```python
import pandas as pd
from battery_simulator import simulate_day

COST_PER_KWH_INSTALLED = 500        # £/kWh installed
BATTERY_SIZES_KWH = [2, 5, 7, 10, 13, 15]
ROUND_TRIP_EFFICIENCY = 0.90
MAX_C_RATE = 0.5
MIN_SOC = 0.20
WARRANTY_YEARS = 15

MPAN = "1234567891000"
DATA_DIR = "data"


def load_data():
    consumption = pd.read_csv(f"{DATA_DIR}/consumption.csv")
    consumption = consumption[
        (consumption["mpxn"] == int(MPAN)) & (consumption["utility"] == "electricity")
    ][["timestamp", "value"]].copy()
    consumption["timestamp"] = pd.to_datetime(consumption["timestamp"])
    consumption = consumption.rename(columns={"value": "consumption_kwh"})
    # deduplicate: keep first reading per timestamp (consumption data has >100% completeness)
    consumption = consumption.drop_duplicates(subset="timestamp", keep="first")

    tariff = pd.read_csv(f"{DATA_DIR}/tariff.csv")
    tariff = tariff[
        (tariff["mpan"] == int(MPAN)) & (tariff["type"] == "unit_rate")
    ][["timestamp", "value"]].copy()
    tariff["timestamp"] = pd.to_datetime(tariff["timestamp"])
    tariff = tariff.rename(columns={"value": "rate_p"})
    tariff = tariff.drop_duplicates(subset="timestamp", keep="first")

    merged = consumption.merge(tariff, on="timestamp", how="inner")
    merged["date"] = merged["timestamp"].dt.date
    return merged


def build_daily_arrays(merged):
    """Return list of (date, consumption_48, tariff_48) for complete 48-slot days only."""
    days = []
    for date, group in merged.groupby("date"):
        group = group.sort_values("timestamp")
        if len(group) != 48:
            continue
        days.append((
            date,
            group["consumption_kwh"].tolist(),
            group["rate_p"].tolist(),
        ))
    return days


def format_row(size, installed_cost, avg_daily_p, annual_gbp, payback, flagged):
    flag = " *" if flagged else "  "
    return (
        f"{size:>10} | "
        f"£{installed_cost:>13,.0f} | "
        f"{avg_daily_p:>14.1f}p | "
        f"£{annual_gbp:>12,.2f} | "
        f"{payback:>11.1f}{flag}"
    )


def main():
    merged = load_data()
    days = build_daily_arrays(merged)

    off_peak = min(merged["rate_p"])
    peak = max(merged["rate_p"])
    date_min = min(d for d, _, _ in days)
    date_max = max(d for d, _, _ in days)

    print(f"Battery Size Analysis — MPAN {MPAN}")
    print(f"Tariff: {off_peak}p off-peak / {peak}p peak  |  Installed cost: £{COST_PER_KWH_INSTALLED}/kWh")
    print(
        f"Days simulated: {len(days):,} ({date_min} to {date_max})  |  "
        f"Efficiency: {ROUND_TRIP_EFFICIENCY * 100:.0f}%  |  "
        f"Min SOC: {MIN_SOC * 100:.0f}%  |  "
        f"Max C-rate: {MAX_C_RATE}C"
    )
    print()

    header = (
        f"{'Size (kWh)':>10} | "
        f"{'Installed Cost':>14} | "
        f"{'Avg Daily Saving':>16} | "
        f"{'Annual Saving':>14} | "
        f"{'Payback (yrs)':>13}"
    )
    divider = "-" * 10 + "-+-" + "-" * 14 + "-+-" + "-" * 16 + "-+-" + "-" * 14 + "-+-" + "-" * 13
    print(header)
    print(divider)

    any_flagged = False
    for size in BATTERY_SIZES_KWH:
        total_saving_p = sum(
            simulate_day(c, t, size, ROUND_TRIP_EFFICIENCY, MAX_C_RATE, MIN_SOC)["daily_saving_p"]
            for _, c, t in days
        )
        avg_daily_p = total_saving_p / len(days)
        annual_gbp = avg_daily_p * 365 / 100
        installed_cost = size * COST_PER_KWH_INSTALLED
        payback = installed_cost / annual_gbp if annual_gbp > 0 else float("inf")
        flagged = payback > WARRANTY_YEARS
        if flagged:
            any_flagged = True
        print(format_row(size, installed_cost, avg_daily_p, annual_gbp, payback, flagged))

    if any_flagged:
        print()
        print(f"* Payback exceeds {WARRANTY_YEARS}-year battery warranty period.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the script and verify output**

```
cd C:\Users\steve\projects\smart_meter
python py/battery_analysis.py
```

Expected: a table with 6 rows (one per battery size). All rows likely flagged `*` — UK residential battery payback is typically 20–30 years at current tariff spreads. If the script errors, check that the `mpxn` column in `consumption.csv` is numeric vs string (the load uses `int(MPAN)` — adjust to `str` if needed).

- [ ] **Step 3: Commit**

```
git add battery_analysis.py
git commit -m "feat: add battery size analysis script"
```

---

## Task 4: Push to remote

- [ ] **Step 1: Push**

```
git push
```

---

## Notes

- The `mpxn` column in `consumption.csv` may be stored as int or string — if `int(MPAN)` causes a KeyError, change both `int(MPAN)` occurrences in `load_data()` to `MPAN` (string comparison).
- The tariff data for MPAN `1234567891000` is constant throughout the period (always 8.78/16.29 based on time of day). Joining on exact timestamp handles this correctly.
- The 273-day overlap (consumption Nov 2024–Apr 2026, tariff to Apr 2026) is the complete usable dataset.

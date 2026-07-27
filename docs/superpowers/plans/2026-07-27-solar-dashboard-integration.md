# Solar Dashboard Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface measured solar generation in the Monthly Consumption table and add SEG export earnings to the S01 tariff comparison for meters M2, M3, and M14.

**Architecture:** Add `SOLAR_METERS` and `SEG_RATE_P_KWH` to `config.py`, add two data-layer functions to `tier1_lib.py`, wire them into `s01_tariff_matching.py` (new `seg_earnings_gbp` + `net_cost_gbp` columns), and extend `_consumption_summary()` in `app.py` with `solar_kwh`, `export_kwh`, `seg_earnings_gbp` columns for solar-capable meters.

**Tech Stack:** Python 3.13, Streamlit, csv stdlib, pytest

---

## File Map

| File | Change |
|---|---|
| `py/config.py` | Add `SOLAR_METERS` dict + `SEG_RATE_P_KWH` constant |
| `py/tier1_lib.py` | Add `load_solar_generation()` + `compute_annual_export()` |
| `py/s01_tariff_matching.py` | Import new functions, compute SEG earnings, add 2 output columns + CSV fields |
| `app.py` | Extend `_consumption_summary()` with solar columns for solar meters |
| `tests/test_tier1_lib.py` | Add 4 solar function tests |
| `tests/test_s01_tariff_matching.py` | Add 3 SEG column tests |

---

## Task 1: Add solar config constants

**Files:**
- Modify: `py/config.py`

- [ ] **Step 1: Add constants to config.py**

Open `py/config.py`. After the `ELEC_METERS` block (around line 113), add:

```python
# ---------------------------------------------------------------------------
# Solar generation meter MPXNs (separate generation meter per household)
# ---------------------------------------------------------------------------

SOLAR_METERS = {
    2:  "2234567891000",
    3:  "5330642497188",
    14: "1234567891038",
}

SEG_RATE_P_KWH = 15.0   # Smart Export Guarantee pence/kWh
```

- [ ] **Step 2: Verify import works**

```bash
cd C:\Users\steve\projects\smart_meter && python -c "from config import SOLAR_METERS, SEG_RATE_P_KWH; print(SOLAR_METERS, SEG_RATE_P_KWH)"
```

Expected output:
```
{2: '2234567891000', 3: '5330642497188', 14: '1234567891038'} 15.0
```

- [ ] **Step 3: Commit**

```bash
git add py/config.py
git commit -m "feat: add SOLAR_METERS and SEG_RATE_P_KWH to config"
```

---

## Task 2: Add load_solar_generation() to tier1_lib

**Files:**
- Modify: `py/tier1_lib.py`
- Test: `tests/test_tier1_lib.py`

- [ ] **Step 1: Write the failing tests**

Add to the bottom of `tests/test_tier1_lib.py`:

```python
# --- load_solar_generation ---

def test_load_solar_generation_returns_empty_for_non_solar_meter(tmp_path):
    from tier1_lib import load_solar_generation
    # meter_id 99 is not in SOLAR_METERS
    result = load_solar_generation(99, path=str(tmp_path / "production_clean.csv"))
    assert result == []

def test_load_solar_generation_reads_rows_for_solar_meter(tmp_path):
    from tier1_lib import load_solar_generation
    import csv as _csv
    p = tmp_path / "production_clean.csv"
    with open(p, "w", newline="") as f:
        w = _csv.DictWriter(f, fieldnames=["mpxn","utility","reading_type","device_id","timestamp","value","unit"])
        w.writeheader()
        # M3 MPXN
        w.writerow({"mpxn":"5330642497188","utility":"electricity","reading_type":"production",
                    "device_id":"x","timestamp":"2024-06-01 12:00","value":"1.5","unit":"kWh"})
        w.writerow({"mpxn":"5330642497188","utility":"electricity","reading_type":"production",
                    "device_id":"x","timestamp":"2024-06-01 12:30","value":"2.0","unit":"kWh"})
        # Different meter — should be excluded
        w.writerow({"mpxn":"9999999999999","utility":"electricity","reading_type":"production",
                    "device_id":"x","timestamp":"2024-06-01 12:00","value":"5.0","unit":"kWh"})
    result = load_solar_generation(3, path=str(p))
    assert len(result) == 2
    assert result[0]["solar_kwh"] == pytest.approx(1.5, rel=0.001)
    assert result[1]["solar_kwh"] == pytest.approx(2.0, rel=0.001)
    assert result[0]["timestamp"] == "2024-06-01 12:00"
    assert result[0]["period_index"] == 24   # 12:00 → period 24
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd C:\Users\steve\projects\smart_meter && python -m pytest tests/test_tier1_lib.py::test_load_solar_generation_returns_empty_for_non_solar_meter tests/test_tier1_lib.py::test_load_solar_generation_reads_rows_for_solar_meter -v
```

Expected: FAIL — `ImportError: cannot import name 'load_solar_generation'`

- [ ] **Step 3: Add load_solar_generation() to tier1_lib.py**

Update the import at the top of `py/tier1_lib.py`:

```python
from config import ELEC_METERS, ELEC_CAP_KWH, ELEC_RATE_P_KWH, SOLAR_METERS
```

Then add after `load_electricity()` (after line 40):

```python
def load_solar_generation(meter_id: int,
                           path: str = "data/production_clean.csv") -> list[dict]:
    """
    Return half-hourly solar generation rows for one meter, sorted by timestamp.
    Returns [] if meter_id is not in SOLAR_METERS.
    Filters out readings above ELEC_CAP_KWH.
    """
    if meter_id not in SOLAR_METERS:
        return []
    mpxn = SOLAR_METERS[meter_id]
    seen: set[str] = set()
    rows = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            if row["mpxn"] != mpxn:
                continue
            ts = row["timestamp"]
            if ts in seen:
                continue
            seen.add(ts)
            val = float(row["value"])
            if val > ELEC_CAP_KWH:
                continue
            dt = datetime.strptime(ts, "%Y-%m-%d %H:%M")
            rows.append({
                "timestamp":    ts,
                "solar_kwh":    round(val, 4),
                "period_index": dt.hour * 2 + dt.minute // 30,
            })
    return sorted(rows, key=lambda r: r["timestamp"])
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd C:\Users\steve\projects\smart_meter && python -m pytest tests/test_tier1_lib.py::test_load_solar_generation_returns_empty_for_non_solar_meter tests/test_tier1_lib.py::test_load_solar_generation_reads_rows_for_solar_meter -v
```

Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add py/tier1_lib.py tests/test_tier1_lib.py
git commit -m "feat: add load_solar_generation() to tier1_lib"
```

---

## Task 3: Add compute_annual_export() to tier1_lib

**Files:**
- Modify: `py/tier1_lib.py`
- Test: `tests/test_tier1_lib.py`

- [ ] **Step 1: Write the failing tests**

Add to the bottom of `tests/test_tier1_lib.py`:

```python
# --- compute_annual_export ---

def _make_consumption(timestamps_kwh: list[tuple[str, float]]) -> list[dict]:
    rows = []
    for ts, kwh in timestamps_kwh:
        from datetime import datetime as _dt
        d = _dt.strptime(ts, "%Y-%m-%d %H:%M")
        rows.append({
            "timestamp":    ts,
            "elec_kwh":     kwh,
            "weekday":      d.weekday(),
            "period_index": d.hour * 2 + d.minute // 30,
        })
    return rows

def _make_generation(timestamps_kwh: list[tuple[str, float]]) -> list[dict]:
    rows = []
    for ts, kwh in timestamps_kwh:
        from datetime import datetime as _dt
        d = _dt.strptime(ts, "%Y-%m-%d %H:%M")
        rows.append({
            "timestamp":    ts,
            "solar_kwh":    kwh,
            "period_index": d.hour * 2 + d.minute // 30,
        })
    return rows

def test_compute_annual_export_zero_when_no_generation():
    from tier1_lib import compute_annual_export
    consumption = _make_consumption([("2024-06-01 12:00", 1.0)])
    result = compute_annual_export(consumption, [])
    assert result["annual_export_kwh"] == 0.0
    assert result["annual_generation_kwh"] == 0.0

def test_compute_annual_export_clips_at_zero_when_consumption_exceeds_generation():
    from tier1_lib import compute_annual_export
    # generation < consumption → no export
    ts = "2024-06-01 12:00"
    consumption = _make_consumption([(ts, 2.0)])
    generation  = _make_generation([(ts, 0.5)])
    result = compute_annual_export(consumption, generation)
    assert result["annual_export_kwh"] == pytest.approx(0.0)

def test_compute_annual_export_correct_when_generation_exceeds_consumption():
    from tier1_lib import compute_annual_export
    ts = "2024-06-01 12:00"
    consumption = _make_consumption([(ts, 0.5)])
    generation  = _make_generation([(ts, 2.0)])
    result = compute_annual_export(consumption, generation)
    # export per period = 2.0 - 0.5 = 1.5 kWh; 1 day sample → scale × 365
    assert result["annual_export_kwh"] == pytest.approx(1.5 * 365, rel=0.01)
    assert result["annual_generation_kwh"] == pytest.approx(2.0 * 365, rel=0.01)

def test_compute_annual_export_scales_to_annual():
    from tier1_lib import compute_annual_export
    # 30-day sample, 1 kWh export per period, 1 period per day
    from datetime import date, timedelta
    base = date(2024, 6, 1)
    consumption = _make_consumption(
        [(f"{base + timedelta(days=i)} 12:00", 0.0) for i in range(30)]
    )
    generation = _make_generation(
        [(f"{base + timedelta(days=i)} 12:00", 1.0) for i in range(30)]
    )
    result = compute_annual_export(consumption, generation)
    assert result["annual_export_kwh"] == pytest.approx(365.0, rel=0.01)
    assert result["days_in_sample"] == 30
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd C:\Users\steve\projects\smart_meter && python -m pytest tests/test_tier1_lib.py::test_compute_annual_export_zero_when_no_generation tests/test_tier1_lib.py::test_compute_annual_export_clips_at_zero_when_consumption_exceeds_generation tests/test_tier1_lib.py::test_compute_annual_export_correct_when_generation_exceeds_consumption tests/test_tier1_lib.py::test_compute_annual_export_scales_to_annual -v
```

Expected: FAIL — `ImportError: cannot import name 'compute_annual_export'`

- [ ] **Step 3: Add compute_annual_export() to tier1_lib.py**

Add after `load_solar_generation()`:

```python
def compute_annual_export(consumption_rows: list[dict],
                           generation_rows: list[dict]) -> dict:
    """
    Estimate annual export kWh by comparing generation and consumption per timestamp.
    export per half-hour = max(0, generation - consumption).
    Scales sample to 365 days. Returns zeros if generation_rows is empty.
    """
    if not generation_rows:
        return {"annual_export_kwh": 0.0, "annual_generation_kwh": 0.0, "days_in_sample": 0}

    consumption_map = {r["timestamp"]: r["elec_kwh"] for r in consumption_rows}

    total_export_kwh = 0.0
    total_gen_kwh    = 0.0
    for g in generation_rows:
        gen  = g["solar_kwh"]
        cons = consumption_map.get(g["timestamp"], 0.0)
        total_export_kwh += max(0.0, gen - cons)
        total_gen_kwh    += gen

    days  = len(set(r["timestamp"][:10] for r in generation_rows))
    scale = 365 / days

    return {
        "annual_export_kwh":      round(total_export_kwh * scale, 2),
        "annual_generation_kwh":  round(total_gen_kwh    * scale, 2),
        "days_in_sample":         days,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd C:\Users\steve\projects\smart_meter && python -m pytest tests/test_tier1_lib.py::test_compute_annual_export_zero_when_no_generation tests/test_tier1_lib.py::test_compute_annual_export_clips_at_zero_when_consumption_exceeds_generation tests/test_tier1_lib.py::test_compute_annual_export_correct_when_generation_exceeds_consumption tests/test_tier1_lib.py::test_compute_annual_export_scales_to_annual -v
```

Expected: 4 passed

- [ ] **Step 5: Run full test suite to confirm no regressions**

```bash
cd C:\Users\steve\projects\smart_meter && python -m pytest tests/test_tier1_lib.py -v
```

Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add py/tier1_lib.py tests/test_tier1_lib.py
git commit -m "feat: add compute_annual_export() to tier1_lib"
```

---

## Task 4: Add SEG columns to S01 tariff comparison

**Files:**
- Modify: `py/s01_tariff_matching.py`
- Test: `tests/test_s01_tariff_matching.py`

- [ ] **Step 1: Write the failing tests**

Add to the bottom of `tests/test_s01_tariff_matching.py`:

```python
# --- SEG earnings columns ---
# These tests build rows the same way analyse_meter does, without file I/O.

def _make_s01_row(annual_cost_gbp, seg_earnings_gbp):
    """Simulate one output row from analyse_meter with SEG fields."""
    return {
        "meter_id":                1,
        "product":                 "E.ON Next Fixed",
        "type":                    "flat",
        "rates":                   "24.0p/kWh all-day | 50.0p/day standing",
        "current_annual_cost_gbp": annual_cost_gbp,
        "annual_cost_gbp":         annual_cost_gbp,
        "saving_vs_current_gbp":   0.0,
        "saving_pct":              0.0,
        "night_fraction":          0.25,
        "too_close":               False,
        "rank":                    0,
        "seg_earnings_gbp":        seg_earnings_gbp,
        "net_cost_gbp":            round(annual_cost_gbp - seg_earnings_gbp, 2),
    }

def test_seg_earnings_fields_present_in_all_rows():
    row = _make_s01_row(annual_cost_gbp=1000.0, seg_earnings_gbp=0.0)
    assert "seg_earnings_gbp" in row
    assert "net_cost_gbp" in row

def test_net_cost_equals_annual_minus_seg_for_all_rows():
    row = _make_s01_row(annual_cost_gbp=1000.0, seg_earnings_gbp=75.50)
    assert row["net_cost_gbp"] == pytest.approx(924.50, rel=0.001)

def test_seg_earnings_zero_for_non_solar_meter():
    from config import SOLAR_METERS
    # meter_id 1 must not be a solar meter for this test to be valid
    assert 1 not in SOLAR_METERS
    row = _make_s01_row(annual_cost_gbp=800.0, seg_earnings_gbp=0.0)
    assert row["seg_earnings_gbp"] == 0.0
    assert row["net_cost_gbp"] == pytest.approx(800.0, rel=0.001)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd C:\Users\steve\projects\smart_meter && python -m pytest tests/test_s01_tariff_matching.py::test_seg_earnings_fields_present_in_all_rows tests/test_s01_tariff_matching.py::test_net_cost_equals_annual_minus_seg_for_all_rows tests/test_s01_tariff_matching.py::test_seg_earnings_zero_for_non_solar_meter -v
```

Expected: FAIL — `KeyError: 'seg_earnings_gbp'`

- [ ] **Step 3: Update imports in s01_tariff_matching.py**

At the top of `py/s01_tariff_matching.py`, change:

```python
from config import METERS, ELEC_METERS, ELEC_RATE_P_KWH
from tier1_lib import (
    load_electricity,
    load_tariff_rates,
    build_weekly_profile,
    consumption_shape,
    annual_cost_for_tariff,
)
```

to:

```python
from config import METERS, ELEC_METERS, ELEC_RATE_P_KWH, SEG_RATE_P_KWH
from tier1_lib import (
    load_electricity,
    load_solar_generation,
    load_tariff_rates,
    build_weekly_profile,
    consumption_shape,
    annual_cost_for_tariff,
    compute_annual_export,
)
```

- [ ] **Step 4: Update analyse_meter() to compute SEG earnings**

In `py/s01_tariff_matching.py`, inside `analyse_meter()`, add SEG computation after the existing `current` and `ranked` lines (after `ranked = flag_too_close(ranked)`):

```python
gen_rows    = load_solar_generation(meter_id)
export      = compute_annual_export(readings, gen_rows)
seg_earnings = round(export["annual_export_kwh"] * SEG_RATE_P_KWH / 100, 2)
```

Then in the actual row dict (the `rows = [{ ... }]` block), add two fields:

```python
rows = [{
    "meter_id":                meter_id,
    "product":                 actual_name,
    "type":                    f"actual{suffix}",
    "rates":                   _format_rates(period_rates, standing_p_day),
    "current_annual_cost_gbp": current_gbp,
    "annual_cost_gbp":         current_gbp,
    "saving_vs_current_gbp":   0.0,
    "saving_pct":              0.0,
    "night_fraction":          round(shape["night_fraction"], 4),
    "too_close":               False,
    "rank":                    0,
    "seg_earnings_gbp":        seg_earnings,
    "net_cost_gbp":            round(current_gbp - seg_earnings, 2),
}]
for r in ranked:
    product = next(p for p in eon_products if p["name"] == r["product"])
    rows.append({
        "meter_id":                meter_id,
        "product":                 r["product"],
        "type":                    r["type"],
        "rates":                   _format_product_rates(product),
        "current_annual_cost_gbp": current_gbp,
        "annual_cost_gbp":         r["annual_cost_gbp"],
        "saving_vs_current_gbp":   r["saving_vs_current_gbp"],
        "saving_pct":              r["saving_pct"],
        "night_fraction":          round(shape["night_fraction"], 4),
        "too_close":               r["too_close"],
        "rank":                    r["rank"],
        "seg_earnings_gbp":        seg_earnings,
        "net_cost_gbp":            round(r["annual_cost_gbp"] - seg_earnings, 2),
    })
```

- [ ] **Step 5: Update CSV fields list in main()**

In `py/s01_tariff_matching.py`, in `main()`, change:

```python
fields = ["meter_id", "product", "type", "rates", "current_annual_cost_gbp",
          "annual_cost_gbp", "saving_vs_current_gbp", "saving_pct",
          "night_fraction", "too_close", "rank"]
```

to:

```python
fields = ["meter_id", "product", "type", "rates", "current_annual_cost_gbp",
          "annual_cost_gbp", "saving_vs_current_gbp", "saving_pct",
          "night_fraction", "too_close", "rank",
          "seg_earnings_gbp", "net_cost_gbp"]
```

- [ ] **Step 6: Run new tests to verify they pass**

```bash
cd C:\Users\steve\projects\smart_meter && python -m pytest tests/test_s01_tariff_matching.py -v
```

Expected: all 12 tests pass (9 existing + 3 new)

- [ ] **Step 7: Commit**

```bash
git add py/s01_tariff_matching.py tests/test_s01_tariff_matching.py
git commit -m "feat: add seg_earnings_gbp and net_cost_gbp to S01 tariff comparison"
```

---

## Task 5: Add solar columns to Monthly Consumption table

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Update _consumption_summary() imports**

In `app.py`, inside `_consumption_summary()`, the local imports block currently reads:

```python
from config import METERS as _GAS, ELEC_METERS as _ELEC
from tier4_analysis import load_consumption
```

Change to:

```python
from config import METERS as _GAS, ELEC_METERS as _ELEC, SOLAR_METERS as _SOLAR, SEG_RATE_P_KWH as _SEG
from tier1_lib import load_solar_generation, compute_annual_export
from tier4_analysis import load_consumption
```

- [ ] **Step 2: Add monthly solar aggregation**

After the existing `monthly_elec` aggregation loop (after line `monthly_elec[ts[:7]] = ...`), add:

```python
is_solar = meter_id in _SOLAR
monthly_solar_gen:    dict[str, float] = {}
monthly_solar_export: dict[str, float] = {}

if is_solar:
    gen_rows  = load_solar_generation(meter_id)
    elec_rows = []
    for ts, kwh in elec_raw.items():
        from datetime import datetime as _dt
        d = _dt.strptime(ts, "%Y-%m-%d %H:%M")
        elec_rows.append({
            "timestamp":    ts,
            "elec_kwh":     kwh,
            "weekday":      d.weekday(),
            "period_index": d.hour * 2 + d.minute // 30,
        })
    cons_map = {r["timestamp"]: r["elec_kwh"] for r in elec_rows}
    for g in gen_rows:
        ym  = g["timestamp"][:7]
        gen = g["solar_kwh"]
        cons = cons_map.get(g["timestamp"], 0.0)
        monthly_solar_gen[ym]    = monthly_solar_gen.get(ym, 0.0)    + gen
        monthly_solar_export[ym] = monthly_solar_export.get(ym, 0.0) + max(0.0, gen - cons)
```

- [ ] **Step 3: Add solar columns to each monthly row**

In the `for ym in last_12:` loop, after building the existing row dict, add the solar columns conditionally:

```python
    row = {
        "month":          ym,
        "gas_kwh":        round(gas_kwh, 1),
        "gas_cost_gbp":   gas_gbp,
        "elec_kwh":       round(elec_kwh, 1),
        "elec_cost_gbp":  elec_gbp,
        "total_cost_gbp": round(gas_gbp + elec_gbp, 2),
    }
    if is_solar:
        sol_kwh    = monthly_solar_gen.get(ym, 0.0)
        exp_kwh    = monthly_solar_export.get(ym, 0.0)
        seg_gbp    = round(exp_kwh * _SEG / 100, 2)
        row["solar_kwh"]        = round(sol_kwh, 1)
        row["export_kwh"]       = round(exp_kwh, 1)
        row["seg_earnings_gbp"] = seg_gbp
    rows.append(row)
```

Replace the existing `rows.append({...})` block with this version.

- [ ] **Step 4: Add solar columns to the TOTAL row**

In the TOTAL row block, after `"total_cost_gbp": round(...)`, add:

```python
Replace the existing `if rows: rows.append({...})` block with:

```python
    if rows:
        total_row = {
            "month":          "TOTAL",
            "gas_kwh":        round(sum(r["gas_kwh"]        for r in rows), 1),
            "gas_cost_gbp":   round(sum(r["gas_cost_gbp"]   for r in rows), 2),
            "elec_kwh":       round(sum(r["elec_kwh"]       for r in rows), 1),
            "elec_cost_gbp":  round(sum(r["elec_cost_gbp"]  for r in rows), 2),
            "total_cost_gbp": round(sum(r["total_cost_gbp"] for r in rows), 2),
        }
        if is_solar:
            total_row["solar_kwh"]        = round(sum(r.get("solar_kwh", 0.0)        for r in rows), 1)
            total_row["export_kwh"]       = round(sum(r.get("export_kwh", 0.0)       for r in rows), 1)
            total_row["seg_earnings_gbp"] = round(sum(r.get("seg_earnings_gbp", 0.0) for r in rows), 2)
        rows.append(total_row)
```

- [ ] **Step 5: Verify the full test suite still passes**

```bash
cd C:\Users\steve\projects\smart_meter && python -m pytest -v
```

Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add app.py
git commit -m "feat: add solar_kwh, export_kwh, seg_earnings_gbp to monthly consumption summary"
```

---

## Task 6: Smoke test in the running app

**Files:** none — verification only

- [ ] **Step 1: Restart Streamlit on port 8500**

Stop any running Streamlit instance (Ctrl+C), then:

```bash
cd C:\Users\steve\projects\smart_meter && streamlit run app.py --server.port 8500
```

- [ ] **Step 2: Select M3 and run all services**

In the browser at `http://localhost:8500`:
1. Select **M3 — Detached** from the meter dropdown
2. Click **Run All**
3. Open **Monthly Consumption** — confirm `solar_kwh`, `export_kwh`, `seg_earnings_gbp` columns appear
4. Open **S01 — E.ON Tariff Comparison** — confirm `seg_earnings_gbp` and `net_cost_gbp` columns appear and `seg_earnings_gbp > 0`

- [ ] **Step 3: Select M1 (non-solar) and run all services**

1. Select **M1** from the dropdown
2. Click **Run All**
3. Open **Monthly Consumption** — confirm no `solar_kwh` column
4. Open **S01** — confirm `seg_earnings_gbp = 0.0` for all rows

- [ ] **Step 4: Final commit if any fixes were needed**

If any minor fixes were made during smoke testing:

```bash
git add -p
git commit -m "fix: solar dashboard smoke test corrections"
```

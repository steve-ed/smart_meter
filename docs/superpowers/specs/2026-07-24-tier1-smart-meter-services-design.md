# Tier 1 Smart Meter Services — Design Spec

Date: 2026-07-24

## Overview

Four Python scripts implementing Tier 1 value-added services from `docs/tier1_smart_meter_only.md`. All services use only half-hourly smart meter data (electricity and gas) from `data/consumption.csv`, the actual tariff rates from `data/tariff.csv`, weather from `data/weather.csv`, and E.ON product definitions from `data/eon_tariffs.json`.

Scripts follow the tier2 pattern: standalone entry points in `py/`, CSV outputs in `data/`, shared utilities in `py/tier1_lib.py`. Stdlib only in new code; `s02` imports the existing `battery_simulator.simulate_day` directly.

## Decisions

| Decision | Choice |
|---|---|
| Supplier scope | E.ON only — three products (Fixed, Drive, Flex) |
| Battery code | Wrap existing `battery_simulator.simulate_day` — no rewrite |
| pandas | Not used in new code; `battery_simulator.py` retains its internals |
| s03 scope | Event detection + appliance evidence only; no ToU shift saving |
| Current tariff baseline | Most-recent rates per MPAN from `data/tariff.csv` |
| Installed battery cost | £700/kWh |
| BUS grant | £7,500 |
| Discount rate | 3.5% |

---

## File Structure

```
py/
  tier1_lib.py              # shared loaders and profile functions
  s01_tariff_matching.py    # Service #1 — E.ON tariff comparison
  s02_battery_sizing.py     # Service #2 — battery payback curve
  s03_disaggregation.py     # Service #3 — appliance load detection
  s04_heat_pump.py          # Service #4 — heat pump suitability

data/
  eon_tariffs.json          # E.ON product definitions (user-editable)

  # outputs
  s01_tariff_matching.csv
  s02_battery_sizing.csv
  s03_disaggregation.csv
  s04_heat_pump.csv

tests/
  test_tier1_lib.py
  test_s01_tariff_matching.py
  test_s02_battery_sizing.py
  test_s03_disaggregation.py
  test_s04_heat_pump.py
```

---

## `tier1_lib.py` — Shared Foundation

No `main()`. Imported by service scripts only.

### Data loaders

**`load_electricity(meter_id: int, path: str = "data/consumption.csv") → list[dict]`**

Reads `consumption.csv`, filters to `utility == "electricity"` for the given meter's MPAN (from `config.METERS`). Returns rows sorted by timestamp:

```python
{
    "timestamp": str,         # "YYYY-MM-DD HH:MM"
    "elec_kwh": float,        # value field (already kWh for electricity)
    "weekday": int,           # 0=Monday … 6=Sunday
    "period_index": int,      # 0–47
}
```

Filters out readings above `ELEC_CAP_KWH` (sentinel/error values from `config`).

**`load_tariff_rates(mpan: str, path: str = "data/tariff.csv") → dict[int, float]`**

Reads `tariff.csv` for the given MPAN, `type == "unit_rate"`. Returns `{period_index: rate_p_per_kwh}` using the most recent rates (latest date per period). Standing charge is returned separately as a float `p/day` from the most recent `type == "standing_charge"` row.

Signature: `load_tariff_rates(mpan) → tuple[dict[int, float], float]`
Returns: `(period_rates, standing_p_day)`

### Profile functions

**`build_weekly_profile(readings: list[dict], weeks: int = 8) → dict[tuple[int,int], float]`**

Accepts the output of `load_electricity`. Uses the most recent `weeks` weeks of data. Returns `{(weekday, period_index): median_elec_kwh}`.

**`consumption_shape(weekly_profile: dict) → dict`**

Returns:
```python
{
    "night_fraction":        float,  # periods 0–13 (00:00–07:00) share of weekly total
    "morning_fraction":      float,  # periods 12–17 (06:00–09:00)
    "evening_peak_fraction": float,  # periods 32–41 (16:00–21:00)
    "annual_kwh_estimate":   float,  # weekly total / 7 * 365
}
```

### Tariff helper

**`rate_for_period(bands: list[dict], period_index: int) → float`**

Evaluates a list of E.ON tariff band dicts `[{"start_period": int, "end_period": int, "rate_p_per_kwh": float}]` and returns the matching rate. Raises `ValueError` if no band covers the period.

**`annual_cost_for_tariff(readings: list[dict], bands: list[dict], standing_p_day: float) → dict`**

Computes total annual cost (unit + standing) scaled to 365 days if sample < 365 days.

Returns:
```python
{
    "total_cost_gbp":    float,
    "unit_cost_gbp":     float,
    "standing_cost_gbp": float,
    "days_in_sample":    int,
}
```

---

## `data/eon_tariffs.json`

User-editable. Three products:

```json
[
  {
    "name": "E.ON Next Fixed",
    "product_type": "flat",
    "standing_p_day": 50.0,
    "bands": [
      {"start_period": 0, "end_period": 47, "rate_p_per_kwh": 24.0}
    ]
  },
  {
    "name": "E.ON Next Drive",
    "product_type": "two_rate",
    "standing_p_day": 50.0,
    "bands": [
      {"start_period": 0,  "end_period": 13, "rate_p_per_kwh": 7.5},
      {"start_period": 14, "end_period": 47, "rate_p_per_kwh": 24.5}
    ]
  },
  {
    "name": "E.ON Next Flex",
    "product_type": "actual",
    "standing_p_day": null,
    "bands": []
  }
]
```

`E.ON Next Flex` with `product_type == "actual"` signals the script to use `tariff.csv` rates as-is (the meter's current/historical rates). `standing_p_day: null` means the actual standing charge from `tariff.csv` is used.

---

## Service Scripts

### s01_tariff_matching.py — E.ON Tariff Comparison

**Inputs:** `data/consumption.csv`, `data/tariff.csv`, `data/eon_tariffs.json`

**Logic:**
1. For each meter, load electricity readings and actual tariff rates
2. Compute `current_cost` using `E.ON Next Flex` (actual rates)
3. For each E.ON product, compute `annual_cost_for_tariff`
4. Rank products by `total_cost_gbp` ascending
5. Compute `saving_vs_current_gbp` and `saving_pct` for each
6. Flag `too_close` if cheapest alternative saving < £20
7. Compute `consumption_shape` and include `night_fraction` in output (explains why Drive ranks well/poorly)

**Console output:** One line per meter — cheapest product, saving vs current, night fraction

**CSV columns:** `meter_id`, `product`, `product_type`, `annual_cost_gbp`, `saving_vs_current_gbp`, `saving_pct`, `night_fraction`, `too_close`, `rank`

---

### s02_battery_sizing.py — Battery Payback Curve

**Inputs:** `data/consumption.csv`, `data/tariff.csv`

**Logic:**
1. Load electricity readings and tariff rates for each meter
2. Group readings by date into daily `(consumption_hh[48], tariff_hh[48])` arrays
3. For each capacity in `[2, 4, 5, 7, 10, 13.5]` kWh, call `battery_simulator.simulate_day()` across all complete days; sum to annualised saving
4. Compute:
   - `installed_cost_gbp = capacity × 700`
   - `payback_years = installed_cost / annual_saving` (inf if saving ≤ 0)
   - `npv_10yr_gbp` at 3.5% discount rate
5. Flag `recommended = True` on the capacity with the shortest finite payback ≤ 15 years

**Battery parameters passed to `simulate_day`:**
- `max_c_rate = min(capacity × 0.5, 3.6) / capacity` (0.5C capped at 3.6 kW)
- `round_trip_efficiency = 0.92`
- `min_soc = 0.10`

**Console output:** Per-meter — recommended capacity, annual saving, payback years

**CSV columns:** `meter_id`, `capacity_kwh`, `installed_cost_gbp`, `annual_saving_gbp`, `payback_years`, `npv_10yr_gbp`, `recommended`

---

### s03_disaggregation.py — Appliance Load Detection

**Inputs:** `data/consumption.csv`

**Logic:**
1. Load electricity readings for each meter; build `weekly_profile` over last 8 weeks
2. Compute residual series: `max(actual_kwh − expected_kwh, 0)` per period
3. Detect contiguous load events where residual ≥ 0.25 kWh; finalise each event with `date`, `start_period`, `end_period`, `duration_periods`, `total_kwh`, `peak_kwh_per_period`, `mean_kwh_per_period`
4. Match each event against 7 appliance signatures using duration, peak power, and time-of-day affinity score (confidence 0–1); threshold ≥ 0.40 to include a match
5. Aggregate per appliance: `match_count`, `mean_confidence`; flag `likely_present` if `match_count ≥ 4` and `mean_confidence ≥ 0.55`

**Appliance signatures:**

| Appliance | Duration (periods) | Peak kWh/period | Affinity periods |
|---|---|---|---|
| ev_fast | 4–48 | 2.5–4.0 | 0–13 (overnight) |
| ev_slow | 8–48 | 1.5–2.0 | 0–13 |
| immersion | 1–6 | 1.3–1.8 | 0–7, 32–39 |
| shower | 1–2 | 0.7–2.8 | 12–19, 34–41 |
| washing | 1–4 | 0.4–1.3 | 14–39 |
| dishwasher | 2–5 | 0.4–1.3 | 36–47 |
| oven | 1–4 | 0.9–1.8 | 30–43 |

**Console output:** Per-meter — list of likely-present appliances with match counts

**CSV columns:** `meter_id`, `appliance`, `match_count`, `mean_confidence`, `likely_present`

---

### s04_heat_pump.py — Heat Pump Suitability Scoring

**Inputs:** `data/consumption.csv`, `data/tariff.csv`, `data/weather.csv`

**Logic:**
1. Load daily gas totals per meter; estimate `base_load_kwh_day` from May–Sep median
2. For each day: `space_heating_kwh = max(total_gas_kwh − base_load, 0)`
3. Join with daily mean temp from `weather.csv`; compute HDD and `kwh_per_hdd`
4. For each half-hourly heating period, compute ASHP electricity needed:
   - `thermal_kwh = gas_kwh × 0.89` (condensing boiler efficiency)
   - `cop = cop_at_outdoor_temp(temp_c, flow_temp)` — Carnot model × 0.45 practical factor, clamped: 1.0 below −10°C, 6.0 if outdoor > flow target
   - `hp_elec_kwh = thermal_kwh / cop`
5. Run twice: `flow_temp = 45` (optimistic) and `flow_temp = 55` (conservative)
6. Compare gas cost (6p/kWh) vs HP electricity cost (meter's actual tariff rates, using same period)
7. Apply BUS grant (£7,500); compute `payback_years` and `npv_15yr_gbp` at 3.5%
8. Compute `breakeven_cop = ELEC_RATE_P_KWH / GAS_RATE_P_KWH`
9. Four suitability flags:
   - `heating_demand`: space heating ≥ 5,000 kWh/year
   - `seasonal_signal`: winter (Oct–Mar) / summer (May–Sep) gas ratio ≥ 2.0
   - `cop_above_breakeven`: mean seasonal COP ≥ breakeven COP
   - `financial_viability`: payback ≤ 15 years and NPV > 0

**Installed cost range:** £10,000–£14,000 (mid-point £12,000 used for payback calculation; report range in console)

**Console output:** Per-meter per scenario — annual saving, payback, viable flag, seasonal COP, breakeven COP

**CSV columns:** `meter_id`, `scenario`, `heating_gas_kwh`, `hp_elec_kwh`, `gas_cost_gbp`, `hp_elec_cost_gbp`, `annual_saving_gbp`, `mean_seasonal_cop`, `breakeven_cop`, `payback_years`, `npv_15yr_gbp`, `viable`, `flag_heating_demand`, `flag_seasonal_signal`, `flag_cop_above_breakeven`, `flag_financial_viability`

---

## Test Coverage

Each test file covers the pure functions of its script (no file I/O):

| Test file | Key functions tested |
|---|---|
| `test_tier1_lib.py` | `build_weekly_profile`, `consumption_shape`, `rate_for_period`, `annual_cost_for_tariff` |
| `test_s01_tariff_matching.py` | `rank_tariffs`, `flag_too_close` |
| `test_s02_battery_sizing.py` | `npv`, `payback_curve` (with mocked `simulate_day`) |
| `test_s03_disaggregation.py` | `compute_residual`, `detect_events`, `match_event`, `aggregate_appliance_evidence` |
| `test_s04_heat_pump.py` | `cop_at_outdoor_temp`, `estimate_base_load`, `heating_kwh`, `heat_pump_payback`, `suitability_flags` |

---

## config.py additions

`config.METERS` maps meter_id → gas MPXN. Electricity uses different MPANs. Add `ELEC_METERS` to `config.py` (confirmed by inspecting `consumption.csv` during Task 1):

```python
ELEC_METERS = {
    1: "<elec_mpan_1>",   # filled in during implementation
    2: "<elec_mpan_2>",
    3: "<elec_mpan_3>",
    4: "<elec_mpan_4>",
    5: "<elec_mpan_5>",
}
```

`tier1_lib.load_electricity` uses `ELEC_METERS[meter_id]` to filter consumption rows.

---

## Implementation Order

1. `tier1_lib.py` + `test_tier1_lib.py`
2. `data/eon_tariffs.json`
3. `s01_tariff_matching.py` + tests (validates tariff loading)
4. `s02_battery_sizing.py` + tests (validates battery wrapper)
5. `s03_disaggregation.py` + tests (independent of gas data)
6. `s04_heat_pump.py` + tests (depends on gas + weather)

## Data Requirements

| Script | Minimum history |
|---|---|
| s01 | 4 weeks electricity |
| s02 | 8 weeks electricity |
| s03 | 8 weeks electricity |
| s04 | 12 months gas + weather.csv coverage |

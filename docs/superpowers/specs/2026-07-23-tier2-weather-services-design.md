# Tier 2 Weather Services — Design Spec

Date: 2026-07-23

## Overview

Six Python scripts implementing the Tier 2 value-added services defined in `docs/tier2_weather.md`. All scripts follow the existing codebase pattern: standalone entry points in `py/`, CSV outputs in `data/`, shared constants in `config.py`. A new shared library `py/tier2_lib.py` provides the HDD regression foundation used by three services.

## Decisions

| Decision | Choice |
|---|---|
| Output | Console summary + CSV files |
| Structure | Separate script per service |
| Service #8 appliances | User-editable `data/appliances.csv` |
| Service #7 budget | Auto-computed from each meter's 12-month average gas spend |
| Carbon region | Hardcoded West Yorkshire (region ID 12) in `config.py` |

---

## File Structure

```
py/
  tier2_lib.py              # shared foundation (no main, never run directly)
  s05_boiler_trending.py
  s06_heating_efficiency.py
  s07_budget_forecast.py
  s08_carbon_shifting.py
  s09_prewarm.py
  s10_leak_frost.py

data/
  appliances.csv            # user-editable input for Service #8

  # outputs (written/overwritten on each run)
  s05_boiler_trending.csv
  s06_heating_efficiency.csv
  s07_budget_forecast.csv
  s08_carbon_shifting.csv
  s09_prewarm.csv
  s10_leak_frost.csv
```

### `config.py` additions

Two new constants added to the existing file:

```python
CARBON_REGION_ID = 12   # West Yorkshire DNO region (National Grid ESO)

METER_META = {
    1: {"property_type": "semi",     "build_era": "1945_1980"},
    2: {"property_type": "semi",     "build_era": "post_1980"},
    3: {"property_type": "detached", "build_era": "post_1980"},
    4: {"property_type": "terraced", "build_era": "pre_1945"},
    5: {"property_type": "semi",     "build_era": "post_1980"},
}
```

`METER_META` is moved here from `tier4_analysis.py` (which imports it back) to make it available to the Tier 2 scripts without a circular dependency.

---

## `tier2_lib.py` — Shared Foundation

No `main()`. Imported by service scripts only.

### Data loaders

- **`load_weather() -> list[dict]`** — reads `data/weather.csv`, returns rows with `timestamp`, `temp_c`, `wind_speed_ms`, `is_forecast`
- **`load_consumption(meter_id: int) -> list[dict]`** — reads `data/consumption.csv` filtered to one meter, returns half-hourly gas kWh rows with `timestamp`, `gas_kwh`

### HDD framework

- **`daily_hdd(mean_temp_c: float) -> float`** — `max(15.5 - mean_temp_c, 0)`
- **`period_hdd(temp_c: float) -> float`** — half-hourly contribution: `max(15.5 - temp_c, 0) / 48`
- **`effective_temp(temp_c, wind_speed_ms) -> float`** — wind-adjusted temperature (0.5°C per 3 m/s above 2 m/s)
- **`fit_hdd_regression(records: list[tuple[float,float]]) -> tuple[float, float, float]`** — OLS on `[(hdd, gas_kwh)]` heating-season days (HDD > 0.5), returns `(slope, intercept, r_squared)`

### Utilities

- **`period_to_time(period_index: int) -> str`** — `"HH:MM"`
- **`time_to_period(hour: int, minute: int) -> int`**
- **`UK_BENCHMARKS: dict`** — kWh/HDD by `(property_type, build_era)` (median, p25, p75)
- **`benchmark_percentile(kwh_per_hdd, property_type, build_era) -> dict`** — returns `percentile`, `band` (efficient/average/inefficient)

---

## Service Scripts

### s05_boiler_trending.py — Boiler Efficiency Trending

**Inputs:** `data/consumption.csv`, `data/weather.csv`

**Logic:**
1. Build daily `(HDD, heating_gas_kwh)` pairs for each meter across two heating seasons (`REGRESSION_START` to `REGRESSION_END`)
2. Split into baseline (first season: Oct–Apr) and recent (past 28 days)
3. Require ≥60 HDD-days in baseline and ≥20 HDD-days (HDD > 0.5) in the past 28 calendar days; otherwise report `insufficient_data`
4. Compute `baseline_kwh_per_hdd` and `recent_kwh_per_hdd`
5. Flag alert if `pct_change > 15%`; severity HIGH if >25%
6. Classify trend using weekly kWh/HDD series: `gradual_trend`, `step_change`, or `stable`

**Console output:** One line per meter — meter ID, baseline, recent, % change, alert status, classification

**CSV columns:** `meter_id`, `baseline_kwh_per_hdd`, `recent_kwh_per_hdd`, `pct_change`, `alert`, `alert_severity`, `trend_type`, `status`

---

### s06_heating_efficiency.py — Heating Efficiency Scoring

**Inputs:** `data/consumption.csv`, `data/weather.csv`, `config.METER_META`

**Logic:**
1. Fit HDD regression per meter on heating-season days (HDD > 0.5, R²≥0.60 required)
2. For each heating day in `WINTER_START`–`WINTER_END`, compute daily efficiency score: `100 × actual / expected`
3. Flag anomalous days: z-score > 2.5, sustained for 3+ consecutive days, wind < 8 m/s
4. Suppress anomalies on very mild days (HDD < 1)
5. Compute `kwh_per_hdd` for the full analysis window and look up peer benchmark percentile

**Console output:** Per-meter summary — R², mean score, anomalous day count, benchmark band and percentile

**CSV columns:** `meter_id`, `date`, `hdd`, `expected_kwh`, `actual_kwh`, `score`, `z_score`, `anomalous`, `anomaly_type`

---

### s07_budget_forecast.py — Degree-Day Budget Forecasting

**Inputs:** `data/consumption.csv`, `data/weather.csv`

**Logic:**
1. Auto-compute monthly budget: mean of the past 12 months' gas spend per meter (gas kWh × `GAS_RATE_P_KWH / 100`)
2. Sum actual spend for the current month to date
3. Use forecast temps from `weather.csv` (`is_forecast=1`) for remaining days; fall back to `CLIMATOLOGICAL_MEAN_C` beyond the forecast window
4. Project remaining-month gas kWh using the meter's HDD regression; produce central, high (+1σ), and low (−1σ) estimates
5. Alert if high projection exceeds budget

**Console output:** Per-meter — budget, actual-so-far, projected total (low/central/high), gap, will-exceed flag, thermostat nudge if over budget

**CSV columns:** `meter_id`, `monthly_budget_gbp`, `actual_so_far_gbp`, `projected_total_gbp`, `projected_high_gbp`, `projected_low_gbp`, `budget_gap_gbp`, `will_exceed`, `thermostat_reduction_c`, `days_remaining`

---

### s08_carbon_shifting.py — Carbon-Aware Demand Shifting

**Inputs:** `data/appliances.csv`, live `carbonintensity.org.uk` API (region 12)

**`data/appliances.csv` format:**
```
meter_id,appliance,typical_kwh,min_periods,earliest_period,latest_period
1,washing_machine,1.0,4,0,30
1,dishwasher,1.2,3,32,47
```

**Logic:**
1. Fetch 48h half-hourly carbon intensity for region 12
2. For each appliance row, find the lowest-carbon contiguous block within `[earliest_period, latest_period]`
3. Also find the lowest-cost block using the flat `ELEC_RATE_P_KWH` (all periods equal, so cost-optimal = any valid window; flagged as `joint_optimal=True` unless a ToU tariff is present)
4. Report carbon saving vs running at the appliance's `earliest_period`

**Console output:** Per-appliance recommendation — best start time, mean carbon intensity, saving vs default

**CSV columns:** `meter_id`, `appliance`, `recommended_start_time`, `mean_carbon_gco2_per_kwh`, `current_carbon_gco2_per_kwh`, `carbon_saving_gco2`, `joint_optimal`

---

### s09_prewarm.py — Heating Pre-Warm Optimisation

**Inputs:** `data/consumption.csv`, `data/weather.csv`

**Logic:**
1. Extract boiler start period each morning (first period in 00:00–12:00 with gas ≥ 0.15 kWh)
2. Pair with 06:00 outdoor temperature for that day; accumulate across `REGRESSION_START`–`REGRESSION_END`
3. Detect smart thermostat: if boiler start std < 2 periods across ≥20 observations, suppress service
4. Fit start-time vs temperature regression; require R² ≥ 0.45 and ≥ 40 observations
5. Use today's 06:00 forecast temp to predict tomorrow's optimal start period

**Console output:** Per-meter — recommended start time, forecast temp, R², uncertainty, or suppression reason

**CSV columns:** `meter_id`, `recommended_start_time`, `recommended_start_period`, `forecast_temp_c`, `r_squared`, `uncertainty_periods`, `smart_thermostat_detected`, `status`

---

### s10_leak_frost.py — Micro-Leak and Frost Detection

**Inputs:** `data/consumption.csv`, `data/weather.csv`

**Logic (micro-leak):**
1. Establish overnight baseline (periods 0–7 and 44–47) from summer months (May–Sep), need ≥30 samples
2. Threshold = max(3× median overnight kWh, 0.05 kWh/period)
3. Alert if ≥6 consecutive overnight periods above threshold

**Logic (frost — vacant):**
1. Treat property as vacant if gas < 0.05 kWh/h for past 12 hours
2. Alert if forecast overnight low < 2°C; CRITICAL if < −3°C

**Logic (frost — occupied, heating failure):**
1. Alert if HDD and time of day suggest boiler should be running but gas < 0.15 kWh/period, and forecast low < 2°C

**Console output:** Per-meter — leak status, frost status, severity, annualised waste estimate

**CSV columns:** `meter_id`, `leak_alert`, `max_consecutive_periods`, `annualised_waste_kwh`, `frost_alert`, `frost_severity`, `forecast_low_c`, `hours_until_minimum`, `status`

---

## Implementation Order

Per `docs/tier2_weather.md` section 10:

1. `tier2_lib.py` — HDD regression foundation (all others depend on it)
2. `s06_heating_efficiency.py` — builds and validates the regression
3. `s05_boiler_trending.py` — uses regression output
4. `s07_budget_forecast.py` — uses regression + forecast weather
5. `s10_leak_frost.py` — independent, build in parallel with #5
6. `s09_prewarm.py` — independent of regression
7. `s08_carbon_shifting.py` — independent, requires network call

## Data Requirements

| Script | Minimum history needed |
|---|---|
| s05 | 2 heating seasons (≥60 HDD-days baseline + ≥20 HDD-days recent) |
| s06 | 1 heating season (≥60 HDD-days, R²≥0.60) |
| s07 | 12 months gas + 14-day weather forecast |
| s08 | None (live API) |
| s09 | 1 heating season (≥40 boiler-start observations, R²≥0.45) |
| s10 (leak) | 3 summer months (≥30 overnight samples) |
| s10 (frost) | None (forecast only) |

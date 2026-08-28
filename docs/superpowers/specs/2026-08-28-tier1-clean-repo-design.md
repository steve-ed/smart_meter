# Design: Tier 1 Clean Repository

**Date:** 2026-08-28  
**Status:** Approved

---

## 1. Goal

Create a new standalone git repository at `C:\Users\steve\projects\tier1\` that contains the Tier 1 smart meter services in a clean, navigable structure. The repository starts with Tier 1 and the Streamlit dashboard, with the package layout designed to grow into Tiers 2–4 without restructuring.

---

## 2. Repository Structure

```
tier1/                              ← new git repo root
├── src/
│   └── smart_meter/
│       ├── __init__.py
│       ├── core/
│       │   ├── __init__.py
│       │   ├── config.py           ← from py/config.py
│       │   ├── weather.py          ← from py/weather.py
│       │   ├── home_model.py       ← from py/home_model.py
│       │   └── battery_simulator.py ← from py/battery_simulator.py
│       ├── tier1/
│       │   ├── __init__.py
│       │   ├── lib.py              ← from py/tier1_lib.py
│       │   ├── tariff.py           ← from py/s01_tariff_matching.py
│       │   ├── battery.py          ← from py/s02_battery_sizing.py
│       │   ├── disaggregation.py   ← from py/s03_disaggregation.py
│       │   └── heat_pump.py        ← from py/s04_heat_pump.py
│       ├── tier2/
│       │   └── __init__.py         ← placeholder
│       ├── tier3/
│       │   └── __init__.py         ← placeholder
│       └── tier4/
│           └── __init__.py         ← placeholder
├── app.py                          ← Streamlit dashboard (tier1 views)
├── tests/
│   ├── core/
│   │   └── (ported from smart_meter/tests/ — core module tests)
│   └── tier1/
│       └── (ported from smart_meter/tests/ — tier1 service tests)
├── data/
│   └── samples/                    ← small anonymized sample files
├── docs/
│   ├── requirements.md             ← data contracts, service I/O, constraints
│   └── tier1.md                    ← feature descriptions and usage guide
├── pyproject.toml
└── README.md
```

---

## 3. Module Mapping

All source files are copied (not moved) from `smart_meter/py/` and imports updated to reflect the new package paths.

| Old path | New path | Notes |
|---|---|---|
| `py/config.py` | `src/smart_meter/core/config.py` | Central meter IDs, rates, location |
| `py/weather.py` | `src/smart_meter/core/weather.py` | Open-Meteo API wrapper |
| `py/home_model.py` | `src/smart_meter/core/home_model.py` | Thermal decay step function |
| `py/battery_simulator.py` | `src/smart_meter/core/battery_simulator.py` | Required by tier1/battery.py |
| `py/tier1_lib.py` | `src/smart_meter/tier1/lib.py` | Shared loaders and profile builders |
| `py/s01_tariff_matching.py` | `src/smart_meter/tier1/tariff.py` | Service #1 |
| `py/s02_battery_sizing.py` | `src/smart_meter/tier1/battery.py` | Service #2 |
| `py/s03_disaggregation.py` | `src/smart_meter/tier1/disaggregation.py` | Service #3 |
| `py/s04_heat_pump.py` | `src/smart_meter/tier1/heat_pump.py` | Service #4 (see note below) |

**Note on s04 (heat pump):** The current implementation imports `tier2_lib` for `load_consumption` and `load_weather`. In the new repo, the weather loading dependency is brought into `core/weather.py` and the gas consumption loader is moved into `tier1/lib.py` — keeping the service self-contained within Tier 1.

---

## 4. Service Contracts

### S01 — Tariff Matching

**Input:** Half-hourly electricity CSV, tariff rates JSON (`data/eon_tariffs.json`)  
**Output:** `data/s01_tariff_matching.csv`

| Column | Type | Description |
|---|---|---|
| meter_id | int | Meter identifier |
| product | str | Tariff product name |
| type | str | `actual`, `fixed`, `drive`, `flex` |
| rates | str | Human-readable rate summary |
| current_annual_cost_gbp | float | Annualised spend on current tariff |
| annual_cost_gbp | float | Annualised spend on this product |
| saving_vs_current_gbp | float | Positive = saving, negative = more expensive |
| saving_pct | float | Percentage saving vs current |
| night_fraction | float | Fraction of consumption 00:00–06:59 |
| too_close | bool | True if best saving < £20 threshold |
| rank | int | 0 = actual tariff, 1 = best alternative |
| seg_earnings_gbp | float | Annual SEG export earnings |
| net_cost_gbp | float | annual_cost minus SEG earnings |

### S02 — Battery Size Optimisation

**Input:** Half-hourly electricity CSV, tariff rates  
**Output:** `data/s02_battery_sizing.csv`

| Column | Type | Description |
|---|---|---|
| meter_id | int | Meter identifier |
| capacity_kwh | float | Battery size swept: 2, 4, 5, 7, 10, 13.5 kWh |
| installed_cost_gbp | float | Capacity × £700/kWh |
| annual_saving_gbp | float | Simulated arbitrage saving per year |
| payback_years | float | Simple payback; `inf` if no saving |
| npv_10yr_gbp | float | Net present value over 10 years at 3.5% |
| recommended | bool | Shortest payback ≤ 15 years |

### S03 — Appliance Load Disaggregation

**Input:** Half-hourly electricity CSV  
**Output:** `data/s03_disaggregation.csv`

| Column | Type | Description |
|---|---|---|
| meter_id | int | Meter identifier |
| appliance | str | `ev_fast`, `ev_slow`, `immersion`, `shower`, `washing`, `dishwasher`, `oven` |
| match_count | int | Number of residual events matched to this appliance |
| mean_confidence | float | Mean match score (0–1) |
| likely_present | bool | True if count ≥ 4 and mean_confidence ≥ 0.55 |

### S04 — Heat Pump Suitability

**Input:** Half-hourly gas CSV, half-hourly electricity CSV, weather data  
**Output:** `data/s04_heat_pump.csv`

| Column | Type | Description |
|---|---|---|
| meter_id | int | Meter identifier |
| scenario | str | `optimistic_45c_flow` or `conservative_55c_flow` |
| heating_gas_kwh | float | Annual heating demand (gas, above summer base load) |
| hp_elec_kwh | float | Estimated annual heat pump electricity consumption |
| gas_cost_gbp | float | Current annual heating cost (gas) |
| hp_elec_cost_gbp | float | Projected heat pump electricity cost |
| annual_saving_gbp | float | gas_cost minus hp_elec_cost |
| mean_seasonal_cop | float | Effective seasonal COP |
| breakeven_cop | float | electricity_rate / gas_rate |
| payback_years | float | Net cost after £7,500 grant / annual saving |
| npv_15yr_gbp | float | NPV over 15 years at 3.5% |
| viable | bool | payback ≤ 15 yrs and NPV > 0 |
| flag_* | bool | Four suitability check flags |

---

## 5. Data Requirements

### 5.1 Current: Static Half-Hourly CSV

**Electricity consumption** (`data/consumption_clean.csv`):

| Column | Type | Format | Notes |
|---|---|---|---|
| mpxn | str | — | Meter Point Administration Number |
| utility | str | `electricity` | Filter on this value |
| timestamp | str | `YYYY-MM-DD HH:MM` | 48 readings per day |
| value | float | kWh | Readings above `ELEC_CAP_KWH` are filtered out |

**Solar generation** (`data/production_clean.csv`):

| Column | Type | Format | Notes |
|---|---|---|---|
| mpxn | str | — | Solar meter identifier |
| timestamp | str | `YYYY-MM-DD HH:MM` | Half-hourly |
| value | float | kWh | Generation in the period |

**Tariff rates** (`data/eon_tariffs.json`): List of product objects, each with `name`, `product_type`, `standing_p_day`, and `bands` (list of `{start_period, end_period, rate_p_per_kwh}`).

**Weather** (loaded via Open-Meteo API or cached CSV): Half-hourly `timestamp`, `temp_c`. Required by S04.

**Minimum data volume:** 7 complete days (48 readings each) per meter for S02. 8 weeks preferred for stable weekly profile building in S01/S03/S04.

### 5.2 Future: Live / Streaming Data

*This section is reserved. Live data integration is a significant workstream and is out of scope for this release.*

Key considerations when this is tackled:
- **Polling cadence:** Smart meter data is typically available with a 24–48 hour lag via the DCC/IHD API; half-hourly resolution requires daily batch pulls, not true streaming.
- **Authentication:** DCC API requires enrollment and OAuth-style credentials per meter.
- **Data normalization:** Live feeds may differ in field names, timezone handling, and gap patterns from the cleaned CSV format used here.
- **Backfill strategy:** First run will need to pull historical data to build the weekly profile window.

---

## 6. Dependencies

```toml
[project]
name = "smart-meter"
requires-python = ">=3.11"

[project.dependencies]
pandas = "*"
plotly = "*"
streamlit = "*"

[project.optional-dependencies]
dev = ["pytest", "pytest-cov"]
```

No external API keys are required for Tier 1 services. S04 (heat pump) uses weather data that is fetched via the Open-Meteo public API (no key required).

---

## 7. Constraints

Tier 1 services explicitly do **not** require:

- Indoor temperature sensors (Tier 4)
- Occupancy detection hardware (Tier 3)
- Proprietary weather data subscriptions (Open-Meteo is free)
- Any cloud infrastructure or database — everything runs locally against flat files

---

## 8. Growth Path

| Tier | Additional requirement | Services added |
|---|---|---|
| 2 | Outdoor temperature (weather API) | Boiler trending, heating efficiency, budget forecast, carbon shifting, pre-warm, leak/frost detection |
| 3 | Occupancy detection | Anomaly suppression, occupancy-adjusted profiles |
| 4 | Indoor temperature sensors | Thermal comfort, zone control, HTC fitting |

Each tier adds a subpackage under `src/smart_meter/tier{n}/` and extends `docs/requirements.md` with its own data contract section.

---

## 9. What Is Not Included

The following modules from `smart_meter/py/` are **not** copied into the new repo for this release:

- `energy_model.py`, `simulation_runner.py` — simulation engine (research tool, not a service)
- `tier2_lib.py`, `tier3_lib.py`, `tier4_analysis.py` — higher-tier service foundations
- `annual_analysis.py`, `battery_analysis.py`, `solar_analysis.py` — ad-hoc analysis scripts
- `anomaly_detector.py`, `occupancy_model.py`, `sensor_model.py` — Tier 3+ concerns
- `appliance_model.py`, `solar_model.py` — simulation components

These remain in the original `smart_meter` repo and will be ported to `tier1` as later tiers are built out.

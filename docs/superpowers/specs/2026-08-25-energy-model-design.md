# Energy Model — Requirements Specification

**Status:** Living spec — see changelog (Section 8) for revision history.

**Scope:** This document defines *what* the parameterised house model must be capable of. It is the single source of truth for model requirements. Implementation detail lives in `docs/home_model.md` and the `py/` source files; this document takes precedence over those where they conflict.

**Not in scope:** Algorithm implementations, data pipeline code, UI design.

**Related docs:**
- `docs/home_model.md` — thermal model implementation
- `docs/tier1_smart_meter_only.md`, `docs/tier2_weather.md`, `docs/tier3_occupancy.md`, `docs/tier4_indoor_temperature.md` — service tier designs
- `docs/value-added-services.md` — feature overview

---

## 1. Purpose and Scope

The energy model is a parameterised synthetic dwelling used to:

1. **Define sensor prerequisites** — declare which sensors each value-added service requires, so that a dwelling instance can be checked for compatibility before a service runs.
2. **Generate ground truth data** — produce synthetic sensor outputs from known parameters, so that value-added services can be validated against a known-correct answer.

The model is not a calibration tool. It does not fit parameters to real data. In production, real sensor data replaces synthetic output; the model is a test harness and a requirements anchor.

---

## 2. Parameter Catalogue

A dwelling instance is fully described by the parameters in this catalogue. Parameters are grouped by domain. Every parameter has a type, unit, and constraints. Parameters marked **(optional)** may be omitted if the corresponding system is absent; their sensor flags must then be set to `false`.

### 2.1 Geometry

| Parameter | Type | Unit | Constraints |
|---|---|---|---|
| `total_floor_area_m2` | float | m² | >0 |
| `storey_height_m` | float | m | >0 |
| `window_area_m2` | float | m² | ≥0, < gross wall area |
| `door_area_m2` | float | m² | ≥0, < gross wall area |
| `plan_aspect_ratio` | float | — | ≥1.0; default 1.0 (square plan) |

`plan_aspect_ratio` is length/width of the rectangular footprint. A value of 1.0 gives a square plan. Two-storey assumed throughout; single-storey requires `total_floor_area_m2 = footprint_m2`.

### 2.2 Fabric and Thermal Properties

| Parameter | Type | Unit | Constraints |
|---|---|---|---|
| `u_wall` | float | W/m²K | >0 |
| `u_roof` | float | W/m²K | >0 |
| `u_floor` | float | W/m²K | >0 |
| `u_window` | float | W/m²K | >0 |
| `u_door` | float | W/m²K | >0 |
| `y_value` | float | W/m²K | ≥0; thermal bridging (SAP Appendix K) |
| `q50` | float | m³/h/m² | >0; air permeability at 50 Pa |
| `kappa` | float | Wh/K/m² | >0; effective thermal mass per floor area |

Typical `kappa` values by construction type:

| Category | kappa (Wh/K/m²) |
|---|---|
| Very light (timber frame) | 75 |
| Light | 110 |
| Medium (cavity brick/block) | 160 |
| Heavy (solid brick) | 240 |
| Very heavy (stone, concrete) | 320 |

### 2.3 Heating System

| Parameter | Type | Unit | Constraints |
|---|---|---|---|
| `heating_fuel` | enum | — | `gas`, `electricity`, `oil`, `hydrogen` |
| `heating_system_type` | enum | — | `boiler`, `heat_pump`, `resistance` |
| `heating_efficiency` | float or curve | — | Single value (0–1 for boiler/resistance) or COP curve `[(outdoor_c, cop), ...]` for heat pump |
| `heat_threshold_kwh` | float | kWh/period | >0; fuel consumption above this = space heating active |
| `t_setpoint` | float | °C | Typically 18–22 |
| `base_load_kwh_per_period` | float | kWh/period | ≥0; non-heating fuel use (hot water, cooking) |

Named system presets:

| Preset ID | System type | Fuel | Default efficiency |
|---|---|---|---|
| `condensing-gas-boiler` | boiler | gas | 0.89 seasonal |
| `ashp` | heat_pump | electricity | COP curve (3.5 at 7°C, 2.5 at −3°C) |
| `electric-resistance` | resistance | electricity | 1.00 |

### 2.4 Solar Generation System (optional)

| Parameter | Type | Unit | Constraints |
|---|---|---|---|
| `solar_present` | bool | — | If false, all other solar parameters are ignored |
| `solar_peak_kw` | float | kWp | >0 |
| `solar_azimuth_deg` | float | ° | 0=N, 90=E, 180=S, 270=W |
| `solar_tilt_deg` | float | ° | 0–90 |
| `solar_performance_ratio` | float | — | 0–1; accounts for shading, inverter loss, soiling |
| `solar_export_metered` | bool | — | Whether export is separately metered |

### 2.5 Battery Storage System (optional)

| Parameter | Type | Unit | Constraints |
|---|---|---|---|
| `battery_present` | bool | — | If false, all other battery parameters are ignored |
| `battery_capacity_kwh` | float | kWh | >0; usable capacity |
| `battery_rte` | float | — | 0–1; round-trip efficiency |
| `battery_charge_rate_kw` | float | kW | >0 |
| `battery_discharge_rate_kw` | float | kW | >0 |

### 2.6 Sensor Configuration

One flag per sensor type. A service requiring a sensor must not run if its flag is `false`.

| Parameter | Type | Corresponding tier |
|---|---|---|
| `sensor_elec_meter` | bool | Tier 1 |
| `sensor_gas_meter` | bool | Tier 1 |
| `sensor_outdoor_temp` | bool | Tier 2 |
| `sensor_wind_speed` | bool | Tier 2 |
| `sensor_occupancy` | bool | Tier 3 |
| `sensor_indoor_temp` | bool | Tier 4 |
| `sensor_solar_generation` | bool | Tier 5 |
| `sensor_battery_state` | bool | Tier 5 |

### 2.7 Occupancy Profile

| Parameter | Type | Unit | Constraints |
|---|---|---|---|
| `occupant_count` | int | — | ≥1 |
| `occupancy_schedule` | dict | — | Per half-hour period index (0–47): `home`, `away`, or `sleep`; separate weekday/weekend schedules |
| `occupancy_source` | enum | — | `synthetic` (from schedule) or `sensor` (from occupancy detector) |

When `occupancy_source = synthetic`, the model generates a deterministic binary (home/away) signal from the schedule and a fixed seed. When `occupancy_source = sensor`, the synthetic signal is replaced by real detector output.

### 2.8 Appliance Signatures

One entry per appliance. The list is extensible; the following are required as named defaults:

| Appliance ID | Rated power (W) | Duty cycle | Daily usage | Seasonal variation |
|---|---|---|---|---|
| `water_heater` | 2000–3000 | Continuous when active | 2–4 × daily | No |
| `fridge` | 100–200 | ~50% (thermostat cycling) | Continuous | Yes (summer +10%) |
| `cooker` | 2000–3000 | Event-based | 1–2 × daily | No |
| `kettle` | 2000–3000 | Short burst (2–4 min) | 4–8 × daily | No |
| `washing_machine` | 1800–2500 | Full cycle (60–90 min) | 0.7 × daily avg | No |
| `dryer` | 2000–4000 | Full cycle (45–60 min) | 0.4 × daily avg | No |
| `shower` | 7000–10500 (electric) | Short burst (5–10 min) | 1 × occupant daily | No |

Each appliance entry exposes these parameters:

| Parameter | Type | Unit |
|---|---|---|
| `rated_power_w` | float | W |
| `duty_cycle` | float or schedule | 0–1 fraction or `[(start, end, on/off), ...]` |
| `daily_frequency` | float | Events/day |
| `seasonal_factor` | float | Multiplier on daily frequency by month |
| `occupancy_correlated` | bool | If true, usage only occurs when `occupancy = home` |

The total synthetic electricity signal is the superposition of all appliance signatures, heating system draw (heat pump and resistance only), solar export offset, and battery charge/discharge.

### 2.9 Weather Inputs

Weather data is shared across all dwelling instances. Parameters specify the data source, not the values themselves.

| Parameter | Type | Default source |
|---|---|---|
| `weather_temp_source` | file path | `data/weather.csv` (column: `outdoor_c`) |
| `weather_wind_source` | file path | `data/weather.csv` (column: `wind_speed_ms`) |
| `weather_irradiance_source` | file path | `data/pvgis_cache_*.json` |

---

## 3. Archetype Presets

An archetype is a named parameter set covering all catalogue entries. Archetypes are defaults — any parameter can be overridden per dwelling instance.

### 3.1 Inheritance Rules

A dwelling instance is declared as:

```yaml
archetype: <id>
overrides:
  <parameter>: <value>
  ...
```

- All parameters not listed in `overrides` inherit from the archetype unchanged.
- Overrides are shallow: only named parameters change.
- Archetype definitions are frozen — existing presets are never modified. Adding a new archetype is a non-breaking change.

### 3.2 Named Archetypes

| Archetype ID | Label | Era | Type | Meter |
|---|---|---|---|---|
| `pre-1919-terraced` | Pre-1919 solid brick terraced | Pre-1919 | Mid-terrace | m4 |
| `1970s-semi` | 1970s cavity brick, unimproved | 1970s | Semi-detached | m1 |
| `1990s-semi` | 1990s cavity brick, partial upgrade | 1990s | Semi-detached | m2 |
| `2005-detached` | 2005 detached, Part L 2002 | 2005 | Detached | m3 |
| `2015-semi` | 2015 semi, Part L 2013 | 2015 | Semi-detached | m5 |

Each archetype defines all parameters in Section 2. The canonical parameter values are in `py/config_m1to5.py`. That file is authoritative for numeric values; this document is authoritative for parameter names, types, and constraints.

### 3.3 Default Sensor Configuration

Each archetype's default sensor set reflects the physical sensors available on its corresponding meter. Overrides can add or remove sensors.

| Archetype | Elec | Gas | Outdoor temp | Wind | Occupancy | Indoor temp | Solar | Battery |
|---|---|---|---|---|---|---|---|---|
| `pre-1919-terraced` | ✓ | ✓ | ✓ | ✓ | — | — | — | — |
| `1970s-semi` | ✓ | ✓ | ✓ | ✓ | — | — | — | — |
| `1990s-semi` | ✓ | ✓ | ✓ | ✓ | — | — | — | — |
| `2005-detached` | ✓ | ✓ | ✓ | ✓ | — | ✓ | ✓ | — |
| `2015-semi` | ✓ | ✓ | ✓ | ✓ | — | — | — | — |

---

## 4. Sensor Tiers

Tiers are cumulative — each tier includes all sensors from tiers below it.

| Tier | Name | Sensors required |
|---|---|---|
| 1 | Meter only | `sensor_elec_meter`, `sensor_gas_meter` |
| 2 | Meter + weather | Tier 1 + `sensor_outdoor_temp`, `sensor_wind_speed` |
| 3 | Meter + weather + occupancy | Tier 2 + `sensor_occupancy` |
| 4 | Meter + weather + occupancy + indoor temp | Tier 3 + `sensor_indoor_temp` |
| 5 | Full | Tier 4 + `sensor_solar_generation`, `sensor_battery_state` |

**Enforcement rule:** The model must verify that a dwelling instance's sensor flags satisfy the tier requirement before a service is allowed to run. A service claiming a tier lower than its actual sensor usage is a spec violation — correct the service tier, not the enforcement rule.

---

## 5. Feature Assessment Matrix

One row per service. Columns:
- **Tier** — minimum sensor tier required
- **Parameters exercised** — which parameter groups the service exercises from the catalogue
- **Ground truth output** — what the model must produce for validation
- **Acceptance criterion** — the quantitative threshold a passing service must meet on synthetic data

| Service | Name | Tier | Parameters exercised | Ground truth output | Acceptance criterion |
|---|---|---|---|---|---|
| s01 | Tariff matching | 1 | Appliance signatures, electricity total | Half-hourly consumption profile | Recommended tariff is lowest-cost option for the synthetic load |
| s02 | Battery sizing | 1 | Appliance signatures, solar (if present), battery | Import/export profile | Recommended capacity within 10% of analytically optimal for synthetic load shape |
| s03 | Disaggregation | 1 | All appliance signatures | Per-appliance event ground truth | Each appliance identified with >70% event-level accuracy |
| s04 | Heat pump scoring | 1 | Heating system type, HTC, COP curve | Heating energy demand vs HTC | Score correctly ranks heat pump viability relative to archetype HTC |
| s05 | Boiler trending | 2 | Heating system, HTC, weather (temp + wind) | Seasonal gas vs HDD relationship | Trend slope within 15% of HTC-derived value |
| s06 | Heating efficiency | 2 | Boiler efficiency, HTC, weather | Efficiency ratio over heating season | Detected efficiency within 10% of modelled boiler efficiency |
| s07 | Budget forecast | 2 | All energy flows, tariff, weather | 12-month cost from synthetic data | Forecast within 5% of cost computed directly from synthetic data |
| s08 | Carbon shifting | 3 | Occupancy profile, appliance signatures | Shiftable load windows | Identified shift windows match occupancy-free periods |
| s09 | Pre-warm | 3 | Occupancy schedule, HTC, τ, weather | Optimal pre-heat start time | Computed start within 1 half-hour period of analytically derived optimum |
| s10 | Leak/frost alert | 3 | Occupancy, indoor temp decay, weather | Alert trigger events (injected faults) | All injected fault events detected; false positive rate <5% |
| s11 | Comfort scoring | 4 | Indoor temp, setpoint, occupancy schedule | Temperature vs setpoint deviation series | Score correlates >0.9 with modelled comfort metric |
| s13 | EPC performance gap | 4 | HTC, τ, indoor temp, weather | Fitted τ vs modelled τ | Fitted τ within ±10% of ground truth τ |
| s14 | Living EPC | 4 | Full parameter set | Rolling HLC estimate over heating season | HLC estimate within 15% of modelled HTC across heating season |
| s15+ | Solar/battery optimisation | 5 | Solar system, battery system, tariff, weather | Dispatch schedule, import/export profile | Acceptance criteria TBD when service is specified |

---

## 6. Ground Truth Requirements

For each sensor type, the model must generate synthetic output meeting these fidelity constraints. Ground truth is used only for validation; real sensor data replaces it in production.

### 6.1 Indoor Temperature

- Half-hourly series from the exact exponential solution to Newton's Law of Cooling (no Euler approximation).
- Must reproduce overnight free-cooling decay events of sufficient depth (≥1°C drop over 6 hours) for τ fitting.
- **Fidelity constraint:** τ fitted from detected decay events must fall within ±10% of τ computed from the parameter set (HTC and kappa).

### 6.2 Electricity Consumption

- Superposition of all appliance signatures + heating draw (heat pump/resistance) − solar export + battery net draw.
- Individual appliance events must be distinguishable at rated-power resolution (±5%) for disaggregation validation.
- **Fidelity constraint:** Sum of all appliance signatures must equal total consumption to within ±2% in any 24-hour window.

### 6.3 Gas Consumption

- Space heating demand derived from HTC, weather, and boiler efficiency, plus constant base load.
- Summer months (May–September): gas represents base load only (hot water, cooking).
- Conversion factor: 11.2 kWh/m³ (from `config.py`), applied consistently.
- **Fidelity constraint:** Synthetic annual gas consumption must be within 10% of the value computed analytically from HTC, degree-days, and base load.

### 6.4 Solar Generation

- Half-hourly generation from PVGIS irradiance data, peak capacity, performance ratio, and orientation parameters.
- Must align to the same timestamp grid as meter data.
- **Fidelity constraint:** Annual synthetic generation within 5% of PVGIS modelled annual yield for the same system specification.

### 6.5 Occupancy

- Deterministic binary (home/away) half-hourly signal from occupancy schedule and a fixed random seed.
- Same seed must produce identical output on repeated runs (reproducibility requirement).
- **Fidelity constraint:** Fraction of home periods in synthetic signal must match schedule-implied fraction within ±2 percentage points per week.

### 6.6 Weather

- Sourced from `data/weather.csv` (outdoor temperature, wind speed) and PVGIS cache (irradiance).
- No synthetic generation: the model consumes real weather data.
- **Fidelity constraint:** Weather data must cover the full simulation period with no gaps longer than 4 consecutive periods. Gaps must be filled by linear interpolation and flagged.

### 6.7 Appliance Signatures

- Each appliance event must occur within the occupancy window if `occupancy_correlated = true`.
- Event timing must be deterministic for a fixed seed.
- **Fidelity constraint:** Per-appliance daily energy within ±10% of rated power × duty cycle × daily frequency.

---

## 7. Derived Quantities

The model must expose these computed values as outputs alongside raw synthetic data. They are used directly by services and validation routines.

| Quantity | Symbol | Unit | Derivation |
|---|---|---|---|
| Envelope area | `envelope_area_m2` | m² | From geometry parameters |
| Net wall area | `wall_net_m2` | m² | Gross wall − window − door |
| Fabric HTC | `fabric_htc` | W/K | ΣU×A over all elements |
| Thermal bridging HTC | `bridging_htc` | W/K | y_value × envelope_area |
| Ventilation HTC | `ventilation_htc` | W/K | From Q50 → ACH → 0.33 × ACH × volume |
| Total HTC | `htc` | W/K | fabric + bridging + ventilation |
| Thermal capacitance | `c_wh_per_k` | Wh/K | kappa × total_floor_area |
| Thermal time constant | `tau_hours` | h | c_wh_per_k / htc |
| Natural ACH | `ach_natural` | h⁻¹ | n50 / 20 (SAP factor) |

---

## 8. Changelog

| Date | Summary | Affects |
|---|---|---|
| 2026-08-25 | Initial spec created. Full parameter catalogue, 5 archetypes, 4 sensor tiers (+ Tier 5 forward-looking), feature matrix for s01–s14, ground truth fidelity constraints. | All |

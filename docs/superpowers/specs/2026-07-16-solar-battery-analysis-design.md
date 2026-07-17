# Solar + Battery Analysis — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the battery arbitrage analysis to simulate a combined solar + battery system overlaid on real metered half-hourly consumption data, sweeping both panel size (kWp) and battery size (kWh).

**Architecture:** Three new files alongside existing code — `solar_profile.py` (generate solar generation arrays), `solar_battery_simulator.py` (per-day dispatch), `solar_analysis.py` (sweep + output). Existing `battery_simulator.py`, `battery_analysis.py`, and tests are untouched.

**Tech Stack:** Python, pandas, requests (PVGIS API), matplotlib (heatmaps + week plots), existing n3rgy API client pattern.

---

## Constraints and Defaults

```python
PANEL_SIZES_KWP      = [2, 4, 6, 8, 10, 12]   # kWp sweep
BATTERY_SIZES_KWH    = [0, 2, 5, 7, 10, 13, 15]  # kWh sweep (0 = solar only, no battery)
SOLAR_COST_PER_KWP   = 900      # GBP/kWp installed
BATTERY_COST_PER_KWH = 500      # GBP/kWh installed (matches battery_analysis.py)
EXPORT_RATE_P        = 15.0     # p/kWh Smart Export Guarantee
PANEL_TILT           = 35       # degrees, standard UK roof pitch
PANEL_AZIMUTH        = 180      # degrees, south-facing
WARRANTY_YEARS       = 15
MIN_SOC              = 0.20
BATTERY_CONFIGS      = [
    {"label": "0.5C", "max_c_rate": 0.5, "rte": 0.92},
    {"label": "1C",   "max_c_rate": 1.0, "rte": 0.88},
]
```

---

## File Structure

| File | Status | Responsibility |
|---|---|---|
| `solar_profile.py` | Create | Generate `date → list[48]` solar generation arrays via PVGIS API or measured sandbox data |
| `solar_battery_simulator.py` | Create | Simulate one day with solar + battery dispatch, return saving metrics |
| `solar_analysis.py` | Create | Sweep panel × battery sizes, load consumption/tariff, produce text tables and plots |
| `data/solar_production.csv` | Create (runtime) | Raw production readings from three sandbox PV MPXNs |
| `battery_simulator.py` | Untouched | Existing battery-only simulation |
| `battery_analysis.py` | Untouched | Existing battery-only analysis |

---

## Solar Profiles

### PVGIS (modelled)

API: `GET https://re.jrc.ec.europa.eu/api/v5_2/seriescalc`

Parameters:
- `lat`, `lon` — from target meter's sandbox postcode
- `peakpower` — 1.0 (normalise to 1 kWp, scale later)
- `angle` — `PANEL_TILT`
- `aspect` — `PANEL_AZIMUTH - 180` (PVGIS convention: 0 = south)
- `outputformat` — `json`
- `pvcalculation` — `1`
- `startyear`, `endyear` — single representative year (e.g. 2023)

Response: hourly `P` (W). Convert: `kWh = P / 1000`. Interpolate each hour to two equal half-hourly slots. Result: `{date: list[48 floats]}` in kWh/kWp. Scale by requested kWp at call time. Cycle across simulation date range by calendar day-of-year.

### Measured (sandbox PV MPXNs)

Pull `production` reading type for MPXNs `2234567891000`, `5330642497188`, `1234567891038` from `https://api-v2-sandbox.data.n3rgy.com` (same chunked GET pattern as `pull_other_meters.py`). Save to `data/solar_production.csv` with columns `mpxn, timestamp, value_kwh`.

Normalise each MPXN:
1. Compute total kWh per calendar year for each MPXN
2. Divide each reading by annual total to get fractional shape (sums to 1 per year)
3. Average the three MPXN shapes to produce a single combined shape
4. Scale: `generation_kwh = shape_value × kWp × 900` (900 kWh/kWp/yr standard UK yield)

Return same `{date: list[48 floats]}` format.

---

## Dispatch Logic (`solar_battery_simulator.py`)

```python
def simulate_day_solar(
    consumption_hh,     # list[48] kWh
    tariff_hh,          # list[48] p/kWh
    solar_hh,           # list[48] kWh generated
    battery_capacity_kwh,
    rte,
    max_c_rate,
    min_soc,
    export_rate_p,
) -> dict
```

Per half-hourly slot:

1. `net_load = consumption - solar` (can be negative = surplus)
2. If `net_load < 0` (solar surplus):
   - Charge battery: `charge = min(surplus, max_hh_kwh, capacity - soc)`
   - `soc += charge`
   - `exported = surplus - charge` → revenue = `exported × export_rate_p`
3. If `net_load >= 0` and `tariff == off_peak`:
   - Grid charges battery (same as existing simulator)
4. If `net_load >= 0` and `tariff == peak`:
   - Battery discharges to cover `net_load`, capped by C-rate, available energy, and `net_load / rte`
5. `grid_draw = max(0, net_load - battery_discharge)`

Returns:
```python
{
    "daily_saving_p": float,         # vs no-solar no-battery baseline
    "solar_self_consumed_kwh": float,
    "solar_exported_kwh": float,
    "peak_kwh_displaced": float,     # from battery discharge at peak
    "grid_draw_kwh": float,
}
```

Saving formula:
```
saving = (baseline_cost - new_cost) + export_revenue
baseline_cost = sum(consumption[i] * tariff[i]) for all i
new_cost = sum(grid_draw[i] * tariff[i]) for all i
export_revenue = solar_exported_kwh * export_rate_p
```

---

## Analysis (`solar_analysis.py`)

Configuration block at top (same pattern as `battery_analysis.py`):

```python
MPAN         = "1234567891024"
METER_NUMBER = 5
LAT          = 53.60    # from meter postcode WF9 2UW
LON          = -1.32
```

### Load data
Same `load_data()` and `build_daily_arrays()` as `battery_analysis.py` (copy verbatim — no import to keep files independent).

### Sweep
For each profile in `["pvgis", "measured"]`:
  For each battery config in `BATTERY_CONFIGS`:
    For each `panel_kWp` in `PANEL_SIZES_KWP`:
      For each `battery_kWh` in `BATTERY_SIZES_KWH`:
        Run `simulate_day_solar()` across all days → aggregate metrics

### Text output (`data/m{N}-solar-results.txt`)

One section per profile × battery config. Table: rows = panel kWp, columns = battery kWh. Each cell: `annual_saving / payback`. Flag cells where payback > WARRANTY_YEARS with `*`.

Example header row:
```
Panel (kWp) |   0 kWh |   2 kWh |   5 kWh |   7 kWh |  10 kWh |  13 kWh |  15 kWh
```

Also print a baseline row (no solar, no battery) at the top of each section.

### Heatmap plots (`data/m{N}-solar-heatmap-{profile}-{config}.png`)

- X axis: battery size (kWh), including 0
- Y axis: panel size (kWp)
- Cell colour: payback period (years), diverging colormap, capped at 20 years
- Cell annotation: `{payback:.1f}yr\n£{annual_saving:.0f}/yr`
- Cells exceeding WARRANTY_YEARS hatched with `/////`
- Contour line at 10-year payback
- Title: `Meter {N} — Solar + Battery Payback ({profile} profile, {config} battery)`

One plot per profile × config = 4 plots total.

### Week plot (`data/m{N}-solar-wk{week_number}.png`)

Four stacked panels sharing x-axis (same week as `battery_week_plot.py` — configurable `WEEK_START`):
1. Solar generation (kWh/hh) — yellow fill
2. Consumption vs net grid draw with battery — blue/purple lines
3. Battery SOC (kWh)
4. Tariff (p/kWh)

Run for a single representative config (e.g. 6 kWp + 5 kWh battery, 0.5C).

---

## Data Files

`.gitignore` additions:
```
data/solar_production.csv
data/*-solar-results.txt
data/*-solar-heatmap-*.png
data/*-solar-wk*.png
```

---

## Error Handling

- PVGIS API: raise with clear message if request fails; cache response to `data/pvgis_cache_{lat}_{lon}_{year}.json` to avoid repeat calls
- Measured profile: if `solar_production.csv` missing, print instructions to run pull script and exit cleanly
- Missing tariff slots: same `dropna` approach as existing `load_data()`

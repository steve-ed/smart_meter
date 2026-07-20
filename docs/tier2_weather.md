# Tier 2 — Weather API Integration: Implementation Guide

Services covered:
- **#5** Boiler Efficiency Trending
- **#6** Heating Efficiency Scoring
- **#7** Degree-Day Budget Forecasting
- **#8** Carbon-Aware Demand Shifting
- **#9** Heating Pre-Warm Optimisation
- **#10** Micro-Leak and Frost Detection

All six services require a free outdoor temperature feed. Services #8 uses a separate carbon intensity API. No physical sensors in the home are required.

---

## 1. Weather Data Layer

### API selection

**Open-Meteo** is recommended as the primary source. It provides historical reanalysis data at hourly resolution from 1940 onwards and a 16-day forecast, free for non-commercial use, with no authentication required.

```
Historical:  https://archive-api.open-meteo.com/v1/archive
Forecast:    https://api.open-meteo.com/v1/forecast
```

**Met Office DataPoint** provides official UK observations and forecasts. Use as a secondary validation source for frost alerts where accuracy matters most.

### Postcode to coordinates

Map the household's postcode to a WGS84 lat/lon centroid. The Office for National Statistics publishes a postcode-to-centroid lookup (ONSPD) updated quarterly. Cache this mapping per household — it changes only if the household moves.

```python
def postcode_to_latlon(postcode: str, onspd: dict[str, tuple[float,float]]) -> tuple[float,float]:
    clean = postcode.replace(' ', '').upper()
    if clean not in onspd:
        raise ValueError(f"Postcode {postcode} not found in ONSPD")
    return onspd[clean]   # (latitude, longitude)
```

### Weather data model

```python
@dataclass
class WeatherPeriod:
    timestamp:       datetime   # UTC, start of period
    period_index:    int        # 0–47 (half-hourly slot)
    temp_c:          float      # dry-bulb air temperature
    wind_speed_ms:   float      # 10m wind speed (for effective temperature)
    precipitation_mm: float
    is_forecast:     bool       # False = historical reanalysis, True = forecast
    forecast_horizon_h: int     # hours ahead; 0 for historical
```

### Downsampling from hourly to half-hourly

Open-Meteo provides hourly data. Split each hour into two half-hourly periods by linear interpolation between adjacent hourly readings:

```python
def hourly_to_half_hourly(hourly: list[tuple[datetime, float]]) -> list[tuple[datetime, float]]:
    result = []
    for i in range(len(hourly) - 1):
        t0, v0 = hourly[i]
        t1, v1 = hourly[i + 1]
        result.append((t0, v0))
        result.append((t0 + timedelta(minutes=30), (v0 + v1) / 2))
    return result
```

For temperature specifically, the linear interpolation is adequate. Do not interpolate precipitation — assign the full hourly value to the first half-hour and zero to the second, to avoid creating spurious drizzle periods.

### Effective temperature

Wind increases heat loss from buildings. Adjust outdoor temperature by an effective temperature correction before computing degree-days:

```python
def effective_temp(temp_c: float, wind_speed_ms: float) -> float:
    """
    Simplified wind chill for building heat loss (not human wind chill).
    Increases apparent coldness by ~0.5°C per 3 m/s wind above 2 m/s.
    Only material for exposed or poorly insulated properties.
    """
    if wind_speed_ms <= 2.0:
        return temp_c
    adjustment = (wind_speed_ms - 2.0) / 3.0 * 0.5
    return temp_c - adjustment
```

This is a pragmatic approximation. Full fabric heat loss models use the EN ISO 13790 convective heat transfer coefficient, which requires wall construction data not available from smart meter data alone.

### Forecast uncertainty model

Forecast accuracy degrades with horizon. Apply a uncertainty envelope when projecting energy costs:

```python
FORECAST_UNCERTAINTY_PER_DAY_C = 0.35   # °C of additional 1-sigma uncertainty per day ahead

def temp_uncertainty_c(horizon_days: float) -> float:
    """1-sigma temperature uncertainty at a given forecast horizon."""
    return FORECAST_UNCERTAINTY_PER_DAY_C * horizon_days ** 0.7
```

Use this in service #7 to produce confidence intervals around projected costs.

---

## 2. Heating Degree-Day Framework

All six services depend on heating degree-days (HDD). Define this once and use it everywhere.

### Standard UK HDD

```python
BASE_TEMP_C = 15.5   # UK Met Office standard base temperature (°C)

def daily_hdd(mean_temp_c: float) -> float:
    return max(BASE_TEMP_C - mean_temp_c, 0.0)

def period_hdd(temp_c: float) -> float:
    """Half-hourly HDD contribution (1/48 of a full day-degree)."""
    return max(BASE_TEMP_C - temp_c, 0.0) / 48
```

### Household-specific HDD–gas regression

The relationship between HDD and gas consumption varies by property. Fit it from historical data using ordinary least squares on daily totals.

```python
def fit_hdd_regression(daily_records: list[tuple[float, float]]) -> tuple[float, float]:
    """
    daily_records: [(hdd, heating_gas_kwh)] — heating-season days only (HDD > 0.5)
    Returns: (slope kWh/HDD, intercept kWh/day)
    The intercept represents non-space-heating gas (hot water, cooking).
    """
    n   = len(daily_records)
    sx  = sum(r[0] for r in daily_records)
    sy  = sum(r[1] for r in daily_records)
    sxx = sum(r[0] ** 2 for r in daily_records)
    sxy = sum(r[0] * r[1] for r in daily_records)

    denom = n * sxx - sx * sx
    if abs(denom) < 1e-9:
        return 0.0, sy / n   # degenerate: no HDD variation
    slope     = (n * sxy - sx * sy) / denom
    intercept = (sy - slope * sx) / n
    return max(slope, 0.0), max(intercept, 0.0)

def r_squared(daily_records: list[tuple[float,float]],
              slope: float, intercept: float) -> float:
    y_mean = sum(r[1] for r in daily_records) / len(daily_records)
    ss_tot = sum((r[1] - y_mean) ** 2 for r in daily_records)
    ss_res = sum((r[1] - (slope * r[0] + intercept)) ** 2 for r in daily_records)
    return 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
```

Report R² alongside results. An R² below 0.70 signals that HDD alone does not explain this household's gas pattern — possibly because occupancy, setpoint behaviour, or a non-condensing boiler introduces significant scatter. Do not produce efficiency scores or budget forecasts for households with R² < 0.60 until more data accumulates.

---

## 3. Service #5 — Boiler Efficiency Trending

### Objective

Detect gradual boiler degradation before it causes a breakdown. A boiler losing efficiency increases gas consumption per unit of heating demand (per HDD) over months. The goal is to detect a 10–15% rise in normalised consumption and alert in time to arrange a service.

### Normalised efficiency metric

The key metric is gas consumed per degree-day:

```
normalised_efficiency_t = heating_gas_kwh_t / HDD_t
```

Where `heating_gas_kwh_t` is the space-heating component of gas (total daily gas minus the summer base load estimate).

This metric has a confound: condensing boilers condense more efficiently at lower return temperatures, which correlates with colder weather. On very cold days (high HDD), the boiler actually operates more efficiently, reducing the kWh/HDD ratio. On mild days (low HDD), the boiler may not reach condensing mode, raising kWh/HDD.

Correct for this with a quadratic term in the regression:

```python
def fit_efficiency_model(records: list[tuple[float, float]]) -> tuple[float, float, float]:
    """
    Fit: gas_kwh = a * HDD + b * HDD^2 + c
    records: [(HDD, heating_gas_kwh)] — heating season days with HDD > 1
    Returns: (a, b, c)
    Uses normal equations for a 3-term polynomial via matrix solve.
    """
    import statistics

    # Simple approach: bin by HDD quartile and compute mean kWh/HDD per bin.
    # Full matrix regression requires numpy — use a two-pass approach instead.

    # Pass 1: simple linear fit
    slope, intercept = fit_hdd_regression(records)

    # Pass 2: fit residuals against HDD to capture curvature
    residuals = [(hdd, gas - (slope * hdd + intercept)) for hdd, gas in records]
    slope2, _ = fit_hdd_regression([(hdd, abs(res)) for hdd, res in residuals])

    return slope, slope2, intercept
```

For production use, replace the two-pass approximation with a proper OLS matrix solve using NumPy's `lstsq`. The two-pass version is shown to clarify the structure without dependencies.

### Rolling baseline and trend detection

Build the efficiency baseline from the first full heating season of data (at least 60 HDD-days). Compare each subsequent rolling 4-week window against that baseline.

```python
TREND_ALERT_THRESHOLD   = 0.15   # 15% rise in kWh/HDD triggers an alert
TREND_MIN_HDD_DAYS      = 20     # minimum HDD-days in comparison window for statistical power
TREND_MIN_BASELINE_DAYS = 60     # minimum HDD-days in baseline for reliable reference

def detect_boiler_degradation(baseline_records: list[tuple[float,float]],
                               recent_records:   list[tuple[float,float]]) -> dict:
    """
    baseline_records: (HDD, heating_gas_kwh) from the reference period
    recent_records:   (HDD, heating_gas_kwh) from the past 28 days
    """
    if (len(baseline_records) < TREND_MIN_BASELINE_DAYS or
            len(recent_records) < TREND_MIN_HDD_DAYS):
        return {'status': 'insufficient_data'}

    baseline_kwh_per_hdd = (sum(g for _, g in baseline_records) /
                             sum(h for h, _ in baseline_records))
    recent_kwh_per_hdd   = (sum(g for _, g in recent_records) /
                             sum(h for h, _ in recent_records))

    pct_change = (recent_kwh_per_hdd - baseline_kwh_per_hdd) / baseline_kwh_per_hdd

    return {
        'baseline_kwh_per_hdd': round(baseline_kwh_per_hdd, 2),
        'recent_kwh_per_hdd':   round(recent_kwh_per_hdd, 2),
        'pct_change':           round(pct_change * 100, 1),
        'alert':                pct_change > TREND_ALERT_THRESHOLD,
        'alert_severity':       'HIGH' if pct_change > 0.25 else 'MEDIUM' if pct_change > 0.15 else None,
    }
```

### Trend vs step change

A gradual efficiency decline is different from a sudden step change (e.g. a heat exchanger failure or a new appliance being added). Distinguish them:

```python
def classify_trend(weekly_kwh_per_hdd: list[float]) -> str:
    """
    weekly_kwh_per_hdd: list of weekly normalised efficiency, chronological.
    Returns 'gradual_trend', 'step_change', or 'stable'.
    """
    if len(weekly_kwh_per_hdd) < 8:
        return 'insufficient_data'

    # Fit linear slope across all weeks
    n = len(weekly_kwh_per_hdd)
    x_mean = (n - 1) / 2
    y_mean = sum(weekly_kwh_per_hdd) / n
    slope_num = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(weekly_kwh_per_hdd))
    slope_den = sum((i - x_mean) ** 2 for i in range(n))
    slope = slope_num / slope_den if slope_den > 0 else 0.0

    # Test for step change: compare first half vs second half
    first_half  = weekly_kwh_per_hdd[:n // 2]
    second_half = weekly_kwh_per_hdd[n // 2:]
    step_ratio  = (sum(second_half) / len(second_half)) / (sum(first_half) / len(first_half))

    if step_ratio > 1.20 and slope < 0.01:
        return 'step_change'       # abrupt jump, not a ramp
    elif slope > 0.008:
        return 'gradual_trend'     # slow ramp upward
    else:
        return 'stable'
```

A step change suggests a specific fault event (scale buildup cleared suddenly, heat exchanger cracked). A gradual trend suggests normal wear or gradual scaling. The alert message should reflect this distinction.

### Minimum data requirement

Boiler degradation operates on a months-to-years timescale. Require at least one full heating season (October–April, ≥ 60 HDD-days) for a baseline, and a second heating season to measure against it. In the first heating season, store data for baseline; defer alerting until the second season.

---

## 4. Service #6 — Heating Efficiency Scoring

### Objective

Produce a per-day efficiency score for each household and benchmark it against similar properties. Surface days where consumption was anomalously high for the outdoor temperature — flagging poor insulation, boiler faults, or behavioural anomalies.

### Daily efficiency score

```python
def daily_efficiency_score(actual_gas_kwh: float, hdd: float,
                            slope: float, intercept: float,
                            slope_std: float) -> dict:
    """
    actual_gas_kwh: total gas consumption for the day
    hdd:            heating degree-days for the day
    slope, intercept: from fit_hdd_regression
    slope_std:      standard deviation of residuals from the regression (in kWh)
    """
    if hdd < 0.5:
        return {'score': None, 'reason': 'too_mild'}   # not a heating day

    expected_kwh = slope * hdd + intercept
    residual_kwh = actual_gas_kwh - expected_kwh
    z_score      = residual_kwh / max(slope_std, 1.0)

    # Score: 100 = exactly as expected. >100 = over-consuming. <100 = more efficient.
    score = round(100 * actual_gas_kwh / expected_kwh, 1) if expected_kwh > 0 else None

    return {
        'score':          score,
        'expected_kwh':   round(expected_kwh, 2),
        'actual_kwh':     round(actual_gas_kwh, 2),
        'residual_kwh':   round(residual_kwh, 2),
        'z_score':        round(z_score, 2),
        'anomalous':      z_score > 2.5,
        'anomaly_type':   'over_consuming' if z_score > 2.5 else 'under_consuming' if z_score < -2.5 else None,
    }
```

### Anomaly triage

Not all anomalous days indicate a fault. Apply a triage checklist before alerting:

| Condition | Likely explanation | Alert? |
|---|---|---|
| Single day z > 2.5, next day normal | Unusual occupancy (guests, home all day) | No |
| 3+ consecutive days z > 2.0 | Boiler issue or window/door left open | Yes |
| Anomaly only in overnight periods | Frost protection firing, or gas leak | Yes (service #10) |
| Anomaly correlates with high wind | Normal — wind chill not fully captured by HDD | Suppress if wind > 8 m/s |
| Anomaly in very mild weather (HDD < 1) | Regression noise at the boundary | Suppress |

```python
def should_alert_anomaly(daily_scores: list[dict],
                          daily_wind_ms: list[float]) -> bool:
    """
    daily_scores: last 3 days of efficiency scores
    daily_wind_ms: mean wind speed for each of those days
    """
    anomalous = [s for s, w in zip(daily_scores, daily_wind_ms)
                 if s.get('anomalous') and w < 8.0 and s.get('score') is not None]
    return len(anomalous) >= 3
```

### Peer benchmarking

Group households by property type, build era, and EPC band. The normalised efficiency metric (kWh/HDD) is the benchmarking unit.

```python
UK_BENCHMARKS = {
    # (property_type, build_era_group): (median kWh/HDD, p25, p75)
    # Approximate values derived from NEED dataset (BEIS)
    ('detached',   'pre_1945'):  (55.0, 42.0, 72.0),
    ('detached',   '1945_1980'): (42.0, 33.0, 54.0),
    ('detached',   'post_1980'): (30.0, 22.0, 40.0),
    ('semi',       'pre_1945'):  (40.0, 31.0, 52.0),
    ('semi',       '1945_1980'): (32.0, 25.0, 42.0),
    ('semi',       'post_1980'): (23.0, 17.0, 30.0),
    ('terraced',   'pre_1945'):  (35.0, 27.0, 46.0),
    ('terraced',   '1945_1980'): (28.0, 21.0, 37.0),
    ('terraced',   'post_1980'): (20.0, 15.0, 27.0),
    ('flat',       'pre_1945'):  (25.0, 18.0, 33.0),
    ('flat',       '1945_1980'): (20.0, 14.0, 28.0),
    ('flat',       'post_1980'): (14.0, 10.0, 19.0),
}

def benchmark_percentile(household_kwh_per_hdd: float,
                          property_type: str,
                          build_era: str) -> dict:
    key = (property_type, build_era)
    if key not in UK_BENCHMARKS:
        return {'percentile': None, 'reason': 'no_benchmark_available'}

    median, p25, p75 = UK_BENCHMARKS[key]

    # Approximate percentile from a log-normal fit to the three known quantiles
    # Simple linear interpolation between known quartiles
    if household_kwh_per_hdd <= p25:
        pct = 25 * household_kwh_per_hdd / p25
    elif household_kwh_per_hdd <= median:
        pct = 25 + 25 * (household_kwh_per_hdd - p25) / (median - p25)
    elif household_kwh_per_hdd <= p75:
        pct = 50 + 25 * (household_kwh_per_hdd - median) / (p75 - median)
    else:
        pct = 75 + 25 * min((household_kwh_per_hdd - p75) / p75, 1.0)

    return {
        'household_kwh_per_hdd': round(household_kwh_per_hdd, 1),
        'peer_median_kwh_per_hdd': median,
        'percentile': round(pct, 0),   # higher = less efficient than peers
        'band': 'efficient' if pct < 33 else 'average' if pct < 67 else 'inefficient',
    }
```

Replace the static `UK_BENCHMARKS` dict with peer data computed from the platform's own consented dataset as it grows. Platform-internal benchmarks will be more precise because they control for geography and meter reading method.

---

## 5. Service #7 — Degree-Day Budget Forecasting

### Objective

Use the household's historical gas/HDD relationship and a 14-day weather forecast to project remaining energy spend for the current month, alerting the consumer before they overspend rather than after.

### Month-remaining projection

```python
from datetime import date, timedelta
import calendar

def project_remaining_month(
        today: date,
        slope: float,
        intercept: float,
        base_load_kwh_day: float,
        forecast_temps: dict[date, tuple[float, float]],   # {date: (mean_temp, std_dev)}
        gas_rate_p_per_kwh: float,
        monthly_budget_gbp: float,
        actual_spend_so_far_gbp: float,
) -> dict:
    """
    forecast_temps: {future_date: (mean_temp_c, 1_sigma_uncertainty_c)}
    Returns projected total month cost with confidence interval.
    """
    days_in_month  = calendar.monthrange(today.year, today.month)[1]
    remaining_days = [today + timedelta(days=i)
                      for i in range(1, days_in_month - today.day + 1)]

    projected_kwh_central  = 0.0
    projected_kwh_high     = 0.0   # 84th percentile (1 sigma colder)
    projected_kwh_low      = 0.0   # 16th percentile (1 sigma warmer)

    daily_projections = []
    for d in remaining_days:
        if d not in forecast_temps:
            # no forecast available — use climatological HDD for this day-of-year
            mean_temp, std_dev = climatological_temp(d), 2.0
        else:
            mean_temp, std_dev = forecast_temps[d]

        hdd_central = daily_hdd(mean_temp)
        hdd_cold    = daily_hdd(mean_temp - std_dev)   # 1σ colder
        hdd_warm    = daily_hdd(mean_temp + std_dev)   # 1σ warmer

        kwh_central = slope * hdd_central + intercept
        kwh_cold    = slope * hdd_cold    + intercept
        kwh_warm    = slope * hdd_warm    + intercept

        projected_kwh_central += kwh_central
        projected_kwh_high    += kwh_cold   # colder = more gas = high projection
        projected_kwh_low     += kwh_warm

        daily_projections.append({
            'date':       d.isoformat(),
            'hdd':        round(hdd_central, 2),
            'kwh':        round(kwh_central, 2),
        })

    total_projected_central_gbp = actual_spend_so_far_gbp + projected_kwh_central * gas_rate_p_per_kwh / 100
    total_projected_high_gbp    = actual_spend_so_far_gbp + projected_kwh_high    * gas_rate_p_per_kwh / 100
    total_projected_low_gbp     = actual_spend_so_far_gbp + projected_kwh_low     * gas_rate_p_per_kwh / 100

    budget_gap_gbp = total_projected_central_gbp - monthly_budget_gbp
    will_exceed    = total_projected_high_gbp > monthly_budget_gbp   # alert if even 1σ projection exceeds

    return {
        'days_remaining':               len(remaining_days),
        'projected_remaining_kwh':      round(projected_kwh_central, 1),
        'projected_total_cost_gbp':     round(total_projected_central_gbp, 2),
        'projected_total_cost_high_gbp':round(total_projected_high_gbp, 2),
        'projected_total_cost_low_gbp': round(total_projected_low_gbp, 2),
        'monthly_budget_gbp':           monthly_budget_gbp,
        'budget_gap_gbp':               round(budget_gap_gbp, 2),
        'will_exceed_budget':           will_exceed,
        'days_until_alert_boundary':    days_remaining_to_alert(remaining_days, slope, intercept,
                                                                 forecast_temps, actual_spend_so_far_gbp,
                                                                 gas_rate_p_per_kwh, monthly_budget_gbp),
        'daily_projections':            daily_projections,
    }
```

### Behavioural nudge calculation

When a budget overrun is projected, calculate the thermostat reduction or schedule change that would bring the month within budget:

```python
def thermostat_nudge(budget_gap_gbp: float,
                     remaining_days: int,
                     gas_rate_p_per_kwh: float,
                     slope: float,
                     mean_forecast_hdd_remaining: float) -> dict:
    """
    Calculate how many degrees of thermostat reduction would close the budget gap.
    Reducing setpoint by ΔT°C reduces effective HDD by ΔT per day.
    """
    gap_kwh = budget_gap_gbp * 100 / gas_rate_p_per_kwh
    if remaining_days == 0 or mean_forecast_hdd_remaining == 0:
        return {}

    kwh_per_degree_day = slope
    degree_reduction_needed = gap_kwh / (kwh_per_degree_day * remaining_days)

    return {
        'thermostat_reduction_c':       round(degree_reduction_needed, 1),
        'budget_gap_kwh':               round(gap_kwh, 1),
        'days_to_implement_by':         remaining_days,
    }
```

A 1°C thermostat reduction reduces heating demand by approximately 8–10% in the UK (CIBSE guidance). Compare the `degree_reduction_needed` result against this rule of thumb as a sanity check; if they diverge significantly, the household's regression slope may be an outlier.

### Climatological fallback

Beyond the 14-day forecast window, use climatological means for the month:

```python
# UK mean temperatures by month (°C) — approx. England average
CLIMATOLOGICAL_MEAN_C = {1: 4.2, 2: 4.5, 3: 6.5, 4: 9.0, 5: 12.0, 6: 15.0,
                          7: 17.0, 8: 16.8, 9: 14.0, 10: 10.5, 11: 7.0, 12: 4.8}

def climatological_temp(d: date) -> float:
    return CLIMATOLOGICAL_MEAN_C[d.month]
```

Replace with postcode-district climatological means from Met Office HadUK-Grid data for better accuracy in Scotland, coastal, and upland areas.

---

## 6. Service #8 — Carbon-Aware Demand Shifting

### Objective

Overlay the National Grid ESO's half-hourly carbon intensity forecast against the household's identified flexible loads to recommend when to run each flexible appliance for minimum carbon footprint, with the tariff cost impact shown alongside.

### Carbon intensity data

```
API: https://api.carbonintensity.org.uk/regional/intensity/{from}/{to}/regionid/{id}
Format: JSON, half-hourly, 48h forecast + historical
Units: gCO2eq/kWh (generated electricity, not consumed — generation-side intensity)
```

Map the household's postcode to a DNO region (14 regions in Great Britain). The ESO publishes a postcode-to-region lookup. Cache the region ID per household.

```python
@dataclass
class CarbonPeriod:
    timestamp:       datetime
    period_index:    int
    intensity_gco2:  float   # gCO2eq/kWh
    is_forecast:     bool

def fetch_carbon_forecast(region_id: int) -> list[CarbonPeriod]:
    """Returns 48h of half-hourly carbon intensity data for the given region."""
    ...   # HTTP call to carbonintensity.org.uk
```

### Flexible load registry

Maintain a per-household registry of identified flexible loads and their constraints:

```python
@dataclass
class FlexibleLoad:
    appliance:          str
    typical_kwh:        float         # energy consumed per use
    min_duration_periods: int         # minimum contiguous periods required
    max_duration_periods: int         # maximum (if variable e.g. EV)
    earliest_start_period: int        # user constraint: not before this period
    latest_end_period:    int         # user constraint: must complete by this period
    detected_frequency:   str         # 'daily' | 'weekdays' | 'weekly'
    source:              str          # 'service3_detected' | 'user_manual'
```

Populate from service #3 detection results. Allow manual user override for any field.

### Optimal scheduling algorithm

For each flexible load, find the contiguous block of periods within the allowed window that minimises total carbon intensity.

```python
def optimal_shift_window(carbon_periods: list[CarbonPeriod],
                          load: FlexibleLoad) -> dict:
    """
    Find the lowest-carbon contiguous block of min_duration_periods within
    [earliest_start_period, latest_end_period].
    """
    window = [cp for cp in carbon_periods
              if load.earliest_start_period <= cp.period_index <= load.latest_end_period
              and not cp.is_forecast or cp.forecast_horizon_h <= 24]

    if len(window) < load.min_duration_periods:
        return {'recommendation': None, 'reason': 'insufficient_window'}

    # sliding window: sum carbon intensity over min_duration_periods
    best_start_idx = 0
    best_carbon    = float('inf')

    for i in range(len(window) - load.min_duration_periods + 1):
        block = window[i : i + load.min_duration_periods]
        # only valid if periods are contiguous (no gap across midnight etc.)
        if block[-1].period_index - block[0].period_index == load.min_duration_periods - 1:
            mean_carbon = sum(p.intensity_gco2 for p in block) / len(block)
            if mean_carbon < best_carbon:
                best_carbon    = mean_carbon
                best_start_idx = i

    best_block = window[best_start_idx : best_start_idx + load.min_duration_periods]

    # current typical period carbon
    typical_period = next((cp for cp in carbon_periods
                           if cp.period_index == _typical_period_for_appliance(load.appliance)), None)
    current_carbon = typical_period.intensity_gco2 if typical_period else best_carbon

    carbon_saving_g = (current_carbon - best_carbon) * load.typical_kwh

    return {
        'appliance':         load.appliance,
        'recommended_start_period': best_block[0].period_index,
        'recommended_start_time':   period_to_time(best_block[0].period_index),
        'recommended_end_time':     period_to_time(best_block[-1].period_index + 1),
        'mean_carbon_intensity':    round(best_carbon, 0),
        'current_carbon_intensity': round(current_carbon, 0),
        'carbon_saving_gco2':       round(carbon_saving_g, 0),
        'duration_periods':         load.min_duration_periods,
    }
```

### Joint optimisation: carbon + cost

For households on a ToU tariff, carbon and cost optima may differ. Present both:

```python
def joint_recommendation(carbon_schedule: dict,
                           cost_schedule: dict,
                           load: FlexibleLoad) -> dict:
    carbon_start = carbon_schedule['recommended_start_period']
    cost_start   = cost_schedule['recommended_start_period']

    if carbon_start == cost_start:
        return {**carbon_schedule, 'joint_optimal': True,
                'message': f"Run at {period_to_time(carbon_start)} — cheapest and lowest carbon."}
    else:
        return {
            'lowest_carbon_start': carbon_schedule['recommended_start_time'],
            'lowest_cost_start':   cost_schedule['recommended_start_time'],
            'carbon_saving_vs_cost_optimal_gco2': round(
                (cost_schedule['mean_carbon_intensity'] - carbon_schedule['mean_carbon_intensity'])
                * load.typical_kwh, 0),
            'cost_penalty_vs_carbon_optimal_p': round(
                (carbon_schedule['mean_carbon_intensity'] - cost_schedule['mean_carbon_intensity'])
                * load.typical_kwh / 1000, 2),   # proxy — replace with actual tariff rate difference
            'joint_optimal': False,
        }
```

### EV charging optimisation

EV charging has a constraint the simpler appliances do not: the required energy is variable (depends on current battery state of charge) and must be completed by a departure time.

```python
def ev_charge_schedule(carbon_periods: list[CarbonPeriod],
                        tariff_periods: list[tuple[int, float]],   # (period_index, rate_p)
                        required_kwh: float,
                        max_charge_kw: float,
                        departure_period: int) -> list[dict]:
    """
    Schedule EV charging to minimise carbon before departure_period.
    Returns list of (period_index, charge_kw) assignments.
    """
    max_kwh_per_period = max_charge_kw * 0.5
    periods_needed     = int(required_kwh / max_kwh_per_period) + 1

    # Rank available periods by carbon intensity up to departure
    available = sorted(
        [(cp.period_index, cp.intensity_gco2,
          next((r for p, r in tariff_periods if p == cp.period_index), 24.0))
         for cp in carbon_periods if cp.period_index < departure_period],
        key=lambda x: x[1]   # sort by carbon ascending
    )

    schedule = []
    remaining = required_kwh
    for period_idx, carbon, rate_p in available[:periods_needed]:
        charge = min(max_kwh_per_period, remaining)
        schedule.append({
            'period_index': period_idx,
            'charge_kwh':   round(charge, 3),
            'carbon_gco2_per_kwh': carbon,
            'rate_p_per_kwh': rate_p,
        })
        remaining -= charge
        if remaining <= 0:
            break

    schedule.sort(key=lambda x: x['period_index'])
    return schedule
```

---

## 7. Service #9 — Heating Pre-Warm Optimisation

### Objective

Recommend the optimal boiler start time each day so that the home reaches the target temperature by the household's arrival or wake-up time, using minimum energy — avoiding both cold returns and wasteful over-heating of an empty house.

### Learning the household's warm-up profile

Without an indoor temperature sensor, learn the relationship from historical gas data. The half-hourly gas signal reveals when the boiler fired each morning. Identify the first heating period each morning:

```python
BOILER_ON_THRESHOLD_KWH = 0.15   # minimum gas per period to count as boiler running (not just pilot)
MORNING_WINDOW = range(0, 24)     # periods 0–23 = 00:00–12:00

def extract_boiler_start(daily_periods: list[tuple[int, float]]) -> int | None:
    """
    daily_periods: [(period_index, gas_kwh)] for one day, sorted by period.
    Returns period_index of first morning boiler-on event, or None.
    """
    for period, kwh in sorted(daily_periods):
        if period in MORNING_WINDOW and kwh >= BOILER_ON_THRESHOLD_KWH:
            return period
    return None
```

Collect (boiler_start_period, mean_outdoor_temp_at_start) pairs over the heating season.

### Regression: start time vs outdoor temperature

The relationship between outdoor temperature and required start time should be roughly linear: colder mornings need an earlier start.

```python
def fit_start_time_model(observations: list[tuple[int, float]]) -> tuple[float, float]:
    """
    observations: [(boiler_start_period, outdoor_temp_c_at_06:00)]
    Returns: (slope periods/°C, intercept period)
    A negative slope means lower temperature → earlier start.
    """
    return fit_hdd_regression([(temp, start) for start, temp in observations])
    # reuses the OLS function from the HDD framework
```

Typical values for a UK semi-detached: start period ≈ 28 – 1.2 × (outdoor_temp). At 5°C → start at period 22 (11:00); at -2°C → start at period 20 (10:00). But start times vary widely by household routine. Learn from each household's data, not from population defaults.

### Daily recommendation

```python
def recommend_start_time(forecast_temp_at_0600: float,
                          slope: float,
                          intercept: float,
                          target_period: int,     # when household needs heat (e.g. period 14 = 07:00)
                          r_squared: float) -> dict:
    """
    target_period: the period by which the home should be warm.
    """
    if r_squared < 0.45:
        return {
            'recommendation': None,
            'reason': 'insufficient_pattern',
            'message': 'Not enough consistent data to predict optimal start time yet.',
        }

    predicted_start = int(round(slope * forecast_temp_at_0600 + intercept))
    predicted_start = max(0, min(predicted_start, target_period - 1))   # clamp: must be before target

    # Uncertainty: ±2 periods (±1 hour) is typical at moderate R²
    uncertainty_periods = max(2, int(4 * (1 - r_squared)))

    return {
        'recommended_start_period': predicted_start,
        'recommended_start_time':   period_to_time(predicted_start),
        'target_period':            target_period,
        'forecast_temp_c':          round(forecast_temp_at_0600, 1),
        'uncertainty_periods':      uncertainty_periods,
        'message': (f"Turn heating on at {period_to_time(predicted_start)} today "
                    f"({forecast_temp_at_0600:.0f}°C forecast)."),
    }
```

### Continuous learning

Update the regression model weekly. Evaluate whether the boiler actually started near the recommended time (within ±2 periods) and whether the heating ran for the expected duration. If the boiler consistently starts much later than recommended, the household's actual routine has shifted and the model should adapt.

```python
def update_observations(observations: list[tuple[int, float]],
                         new_observation: tuple[int, float],
                         max_history: int = 120) -> list[tuple[int, float]]:
    """Keep at most max_history observations (approx. one heating season)."""
    observations.append(new_observation)
    return observations[-max_history:]
```

### Complication: smart thermostats

If the household has a smart thermostat (Hive, Nest, Tado), it is already doing start-time optimisation. Detect this from the gas pattern: if boiler start times are already tightly clustered and do not vary much with temperature, a TPI (time-proportional-integral) controller is likely in place. In this case, service #9 adds no value and should be suppressed.

```python
def is_smart_thermostat_present(observations: list[tuple[int, float]]) -> bool:
    """
    If boiler start times have low variance (std < 2 periods) regardless of temperature,
    a smart thermostat is likely managing scheduling already.
    """
    if len(observations) < 20:
        return False
    starts = [o[0] for o in observations]
    mean   = sum(starts) / len(starts)
    std    = (sum((s - mean) ** 2 for s in starts) / len(starts)) ** 0.5
    return std < 2.0
```

---

## 8. Service #10 — Micro-Leak and Frost Detection

### Micro-leak detection

A slow gas leak, a dripping hot tap keeping the cylinder warm, or a continuously firing pilot light all produce the same half-hourly signature: low-level non-zero gas consumption during periods when the boiler should be off.

#### Establishing the overnight baseline

The "should-be-off" window is overnight and in summer. The baseline overnight gas rate is learned from summer data (May–September), when no space heating is running.

```python
OVERNIGHT_PERIODS = list(range(0, 8)) + list(range(44, 48))  # 00:00–04:00 and 22:00–24:00

SUMMER_MONTHS = {5, 6, 7, 8, 9}

def overnight_baseline_kwh(readings: list[tuple[date, int, float]]) -> dict:
    """
    Compute overnight gas statistics from summer months.
    Returns baseline statistics including the 'expected' low-level consumption.
    """
    overnight_vals = [kwh for d, period, kwh in readings
                      if d.month in SUMMER_MONTHS and period in OVERNIGHT_PERIODS
                      and kwh is not None]

    if len(overnight_vals) < 30:
        return {'status': 'insufficient_data'}

    overnight_vals.sort()
    n = len(overnight_vals)
    return {
        'median_kwh':  overnight_vals[n // 2],
        'p95_kwh':     overnight_vals[int(n * 0.95)],
        'p99_kwh':     overnight_vals[int(n * 0.99)],
        'sample_count': n,
    }
```

#### Micro-leak detection logic

```python
LEAK_SUSTAINED_PERIODS  = 6    # 3 consecutive hours of above-baseline overnight gas
LEAK_THRESHOLD_MULTIPLE = 3.0  # overnight gas must be > 3× baseline median to flag

def detect_gas_leak(overnight_readings: list[float],
                    baseline: dict) -> dict:
    """
    overnight_readings: gas kWh for each of the past N overnight periods, chronological.
    """
    threshold = max(baseline['median_kwh'] * LEAK_THRESHOLD_MULTIPLE,
                    0.05)   # absolute minimum: 0.05 kWh per period (100W equivalent)

    above_threshold = [v >= threshold for v in overnight_readings]
    consecutive_count = 0
    max_consecutive   = 0

    for flag in above_threshold:
        if flag:
            consecutive_count += 1
            max_consecutive = max(max_consecutive, consecutive_count)
        else:
            consecutive_count = 0

    alert = max_consecutive >= LEAK_SUSTAINED_PERIODS
    mean_excess = (
        sum(v - baseline['median_kwh'] for v in overnight_readings if v >= threshold)
        / max(sum(1 for v in overnight_readings if v >= threshold), 1)
    )

    return {
        'alert':              alert,
        'max_consecutive_periods': max_consecutive,
        'threshold_kwh':      round(threshold, 4),
        'mean_excess_kwh':    round(mean_excess, 4),
        'annualised_waste_kwh': round(mean_excess * len(OVERNIGHT_PERIODS) * 365, 0) if alert else 0,
        'possible_causes':    _triage_leak_causes(mean_excess) if alert else [],
    }

def _triage_leak_causes(mean_excess_kwh: float) -> list[str]:
    causes = []
    if mean_excess_kwh < 0.03:
        causes.append('pilot_light_or_standing_charge_artefact')
    if 0.02 <= mean_excess_kwh <= 0.15:
        causes.append('hot_water_cylinder_heat_loss_or_dripping_tap')
    if mean_excess_kwh >= 0.08:
        causes.append('slow_gas_leak_or_appliance_fault')
    if mean_excess_kwh >= 0.20:
        causes.append('boiler_misfiring_or_frost_protection_active')
    return causes
```

The threshold multiple of 3× is conservative. A real gas meter pilot light consumes ~0.02 kWh/period — well below 3× the median for any property with summer baseline above ~0.007 kWh/period. Set to 2× for more sensitivity at the cost of more false positives from boiler frost-protection firing.

### Frost detection and pipe burst prevention

Frost alerts have two distinct triggers:

**Trigger A: Vacant property + forecast sub-zero**

The property appears vacant (gas flat-line for > 12 hours) and the forecast overnight low drops below a threshold.

```python
FROST_RISK_TEMP_C      =  2.0   # °C: below this, unheated pipes can freeze within hours
PIPE_BURST_TEMP_C      = -3.0   # °C: below this, pipe burst risk within 4–6 hours without heating
VACANT_THRESHOLD_HOURS = 12     # hours of zero gas before treating as vacant

def frost_alert(recent_gas_kwh: list[float],
                overnight_forecast_low_c: float,
                forecast_min_period: int) -> dict:
    """
    recent_gas_kwh: hourly gas totals for the past 12 hours.
    overnight_forecast_low_c: minimum forecast temperature in next 24h.
    forecast_min_period: period index when the minimum temperature is forecast.
    """
    apparent_vacant = all(g < 0.05 for g in recent_gas_kwh)

    if overnight_forecast_low_c >= FROST_RISK_TEMP_C:
        return {'alert': False}

    if not apparent_vacant:
        return {'alert': False, 'reason': 'heating_has_been_active'}

    severity = 'CRITICAL' if overnight_forecast_low_c < PIPE_BURST_TEMP_C else 'HIGH'

    hours_until_risk = max((forecast_min_period - _current_period()) * 0.5, 1)

    return {
        'alert':                True,
        'severity':             severity,
        'forecast_low_c':       round(overnight_forecast_low_c, 1),
        'hours_until_minimum':  round(hours_until_risk, 1),
        'last_heating_hours_ago': _hours_since_last_heating(recent_gas_kwh),
        'action':               'Set heating to minimum 10°C or ask neighbour to check property.',
    }
```

**Trigger B: Occupied property with heating failure**

The property is occupied (service #3 / Tier 3 signal, or daytime consumption indicates presence) but the boiler has not fired during a period when it should have, and frost is forecast.

```python
def heating_failure_frost_alert(expected_heating: bool,
                                 actual_gas_kwh: float,
                                 outdoor_temp_c: float,
                                 forecast_low_c: float) -> dict:
    """
    expected_heating: True if HDD and time of day suggest the boiler should be running.
    """
    boiler_absent = actual_gas_kwh < BOILER_ON_THRESHOLD_KWH

    if not (expected_heating and boiler_absent and forecast_low_c < FROST_RISK_TEMP_C):
        return {'alert': False}

    return {
        'alert':          True,
        'severity':       'HIGH',
        'alert_type':     'heating_failure_with_frost_risk',
        'outdoor_temp_c': round(outdoor_temp_c, 1),
        'forecast_low_c': round(forecast_low_c, 1),
        'action':         'Boiler appears off. Check boiler pressure and power before overnight frost.',
    }
```

### Alert deduplication and suppression

Frost alerts should not repeat every half-hour throughout a cold night once issued. Rules:

- Open one frost alert per vacancy episode; do not reopen until the property heats again.
- Suppress leak alerts during periods when a smart thermostat frost-protection mode is known to be active (if the household has declared a smart thermostat in their profile).
- Suppress leak alerts on the first night after a service engineer visit (a boiler service temporarily increases overnight gas readings as it runs test cycles).

---

## 9. Shared Utilities

```python
def period_to_time(period_index: int) -> str:
    hour   = period_index // 2
    minute = (period_index % 2) * 30
    return f"{hour:02d}:{minute:02d}"

def time_to_period(hour: int, minute: int) -> int:
    return hour * 2 + minute // 30

def _current_period() -> int:
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    return time_to_period(now.hour, now.minute)

def _hours_since_last_heating(hourly_gas: list[float]) -> float:
    for i, g in enumerate(reversed(hourly_gas)):
        if g >= 0.10:
            return i
    return len(hourly_gas)
```

---

## 10. Implementation Order and Dependencies

```
Service #6  Heating Efficiency Scoring       ← requires HDD regression (build first)
Service #5  Boiler Efficiency Trending       ← depends on #6's regression output
Service #7  Budget Forecasting               ← depends on #6's regression + weather forecast API
Service #9  Pre-Warm Optimisation            ← depends on boiler start-time extraction from gas data
Service #10 Micro-Leak and Frost Detection   ← independent; build in parallel with #5
Service #8  Carbon-Aware Demand Shifting     ← independent of weather; depends on service #3 appliance list
```

Build the HDD regression framework first. It is the shared foundation for services #5, #6, and #7. Services #8 and #10 can be built independently in parallel.

---

## 11. Minimum Data Requirements

| Service | Minimum history | Key dependency |
|---|---|---|
| #5 Boiler Efficiency Trending | 2 full heating seasons | One season baseline + one to compare |
| #6 Heating Efficiency Scoring | 1 heating season (≥ 60 HDD-days) | HDD regression R² ≥ 0.60 |
| #7 Budget Forecasting | 1 heating season + weather API | Regression + 14-day forecast |
| #8 Carbon-Aware Demand Shifting | 4 weeks (for appliance detection) | Service #3 output + ESO API |
| #9 Pre-Warm Optimisation | 1 heating season (≥ 40 boiler-start observations) | Boiler start extraction |
| #10 Micro-Leak Detection | 3 summer months (for baseline) | Overnight baseline established |
| #10 Frost Detection | None (uses forecast only) | Weather forecast API |

Frost detection from service #10 is the only service that can deliver value from day one of onboarding, with zero historical data required. Prioritise it in the rollout sequence.

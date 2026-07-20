# Tier 4 — Indoor Temperature Sensor: Implementation Guide

Services covered:
- **#13** Thermal Mass / Insulation Decay Profiling
- **#13a** EPC Enhancement — Measured vs Modelled Performance Gap
- **#13b** EPC Enhancement — Continuous / Dynamic EPC
- **#13c** EPC Enhancement — Retrofit Impact Verification
- **#13d** EPC Enhancement — Green Mortgage and Valuation Support
- **#13e** EPC Enhancement — National Housing Stock Carbon Accuracy
- **#14** Comfort vs Cost Trade-Off Reporting

All services require an indoor temperature sensor. Services #13a–#13e additionally require the outdoor temperature feed established in Tier 2. Service #14 benefits from occupancy data from Tier 3 but can operate without it.

---

## 1. Physical Foundation

All Tier 4 services derive from a single physical model: Newton's Law of Cooling applied to a building.

### The first-order building model

When a building's heating system is off and no significant internal heat sources are present, the indoor temperature decays towards the outdoor temperature following an exponential curve:

```
T_indoor(t) = T_outdoor + (T_indoor_0 - T_outdoor) × exp(−t / τ)
```

Where:
- `T_indoor_0` — indoor temperature at the moment heating turns off (°C)
- `T_outdoor` — outdoor temperature, assumed approximately constant during the decay window (°C)
- `τ` — thermal time constant of the building (hours)
- `t` — time elapsed since heating turned off (hours)

The thermal time constant is defined as:

```
τ = C / HLC
```

Where:
- `C` — effective thermal capacitance of the building (Wh/K): the energy required to raise the building's temperature by 1°C
- `HLC` — heat loss coefficient (W/K): the rate of heat loss per degree of indoor-outdoor temperature difference

A larger `τ` means slower decay — better insulation or greater thermal mass. This single number encodes the building's heat retention quality and is the central output of service #13.

### Why half-hourly data is sufficient

At half-hourly intervals, a free cooling event lasting 4–12 hours (8–24 data points) is enough to fit the exponential decay with adequate precision, provided the indoor-outdoor temperature difference is large enough (> 3°C) and the outdoor temperature is approximately stable. The minimum viable decay event is 4 periods (2 hours) with a ΔT > 5°C at the start of the event.

### The performance gap

A SAP EPC assessment estimates HLC from construction type, U-values, and dimensions — it is a modelled prediction. The measured HLC from sensor data is the actual performance. The difference is the performance gap:

```
performance_gap_pct = (HLC_measured − HLC_SAP) / HLC_SAP × 100
```

A positive performance gap means the building loses heat faster than the EPC predicts — it performs worse than rated. UK research consistently finds gaps of 30–50% for pre-1980 stock.

---

## 2. Sensor Requirements

### Indoor temperature sensor specification

| Parameter | Minimum | Recommended |
|---|---|---|
| Accuracy | ±0.5°C | ±0.2°C |
| Resolution | 0.1°C | 0.1°C |
| Sampling interval | 30 min | 5 min (aggregated to 30 min) |
| Connectivity | Bluetooth (local gateway) | WiFi or Zigbee (direct cloud) |
| Battery life | 6 months | 12+ months |

A sensor sampling more frequently than 30 minutes gives a cleaner decay curve. Store raw high-frequency readings and downsample to 30-minute averages for alignment with the meter data.

### Sensor placement

The sensor must be placed in the primary occupied zone — typically the living room or hall — away from:
- Direct sunlight (solar gain will inflate readings)
- Radiators or air vents (localised heat)
- Exterior walls at floor level (localised cold)
- Kitchens (cooking heat) and bathrooms (steam and humidity)
- Draught sources (doors to unheated spaces)

A poorly placed sensor produces a biased HLC estimate. Flag placement issues from the data: if the sensor reading diverges sharply from the household's historical profile at times correlated with cooking patterns, the sensor is likely in or adjacent to the kitchen.

### Data model

```python
@dataclass
class IndoorReading:
    timestamp:    datetime   # UTC, start of period
    period_index: int        # 0–47
    temp_c:       float      # °C, mean over the period
    temp_min_c:   float      # °C, minimum in period (if sub-period sampling available)
    temp_max_c:   float      # °C, maximum in period
    quality:      str        # 'good' | 'estimated' | 'missing'
```

---

## 3. Data Alignment

Three data streams must be aligned to the same half-hourly grid before any analysis:

| Stream | Source | Native resolution |
|---|---|---|
| Indoor temperature | Sensor | 5–30 min |
| Gas consumption | Smart meter | 30 min |
| Outdoor temperature | Open-Meteo (Tier 2) | 60 min → interpolated to 30 min |

Alignment rule: all values are assigned to the period in which they begin. A sensor reading at 14:47 belongs to period 29 (14:30–15:00). Apply the same floor-to-boundary rule used in Tier 2 and Tier 3.

```python
def align_streams(indoor: list[IndoorReading],
                  gas:    list[tuple[datetime, float]],
                  outdoor: list[tuple[datetime, float]]) -> list[dict]:
    """
    Returns list of aligned period records, one per half-hour period.
    Periods missing any stream are flagged quality='incomplete'.
    """
    indexed = {}

    for r in indoor:
        key = (r.timestamp.date(), r.period_index)
        indexed.setdefault(key, {})['indoor_c'] = r.temp_c

    for ts, kwh in gas:
        period = ts.hour * 2 + ts.minute // 30
        key    = (ts.date(), period)
        indexed.setdefault(key, {})['gas_kwh'] = kwh

    for ts, temp in outdoor:
        period = ts.hour * 2 + ts.minute // 30
        key    = (ts.date(), period)
        indexed.setdefault(key, {})['outdoor_c'] = temp

    result = []
    for (d, p), vals in sorted(indexed.items()):
        record = {'date': d, 'period': p, **vals}
        record['complete'] = all(k in vals for k in ('indoor_c', 'gas_kwh', 'outdoor_c'))
        result.append(record)

    return result
```

---

## 4. Service #13 — Thermal Mass / Insulation Decay Profiling

### Step 1: Identify free cooling events

A free cooling event is a contiguous block of periods satisfying all of the following:

```python
BOILER_OFF_THRESHOLD_KWH = 0.05   # gas per period — below this, boiler is off
MIN_DELTA_T_C             = 3.0   # minimum indoor-outdoor difference to start a decay
MIN_DECAY_PERIODS         = 4     # minimum event length (2 hours)
MAX_TEMP_RISE_PERMITTED_C = 0.3   # if indoor temp rises by more than this, internal gains present

def find_free_cooling_events(periods: list[dict]) -> list[list[dict]]:
    """
    Returns list of events, each a list of aligned period dicts.
    """
    events = []
    current = []

    for p in periods:
        if not p['complete']:
            if current and len(current) >= MIN_DECAY_PERIODS:
                events.append(current)
            current = []
            continue

        boiler_off  = p['gas_kwh'] < BOILER_OFF_THRESHOLD_KWH
        cooling     = (p['indoor_c'] - p['outdoor_c']) > MIN_DELTA_T_C
        not_rising  = True   # check against previous period below

        if current:
            prev = current[-1]
            rising_too_fast = (p['indoor_c'] - prev['indoor_c']) > MAX_TEMP_RISE_PERMITTED_C
            not_rising = not rising_too_fast

        if boiler_off and cooling and not_rising:
            current.append(p)
        else:
            if len(current) >= MIN_DECAY_PERIODS:
                events.append(current)
            current = []

    if len(current) >= MIN_DECAY_PERIODS:
        events.append(current)

    return events
```

Prefer overnight events (periods 0–11) for the cleanest decay signal: no solar gain, minimal occupant heat, and the boiler is typically off for a long uninterrupted stretch.

Exclude events where the outdoor temperature varies by more than 2°C during the event — the single-constant-outdoor-temperature assumption breaks down and biases the fit.

### Step 2: Fit the exponential decay

For each event, fit the model:

```
ln(T_indoor[i] − T_outdoor_mean) = ln(A) − i × Δt / τ
```

This is a linear regression on the log-transformed temperature differential.

```python
import math

def fit_tau(event: list[dict], dt_hours: float = 0.5) -> dict | None:
    """
    event: list of aligned period dicts with indoor_c and outdoor_c.
    dt_hours: time step (0.5 for half-hourly data).
    Returns dict with tau_hours, r_squared, and fit quality flags.
    """
    outdoor_mean = sum(p['outdoor_c'] for p in event) / len(event)
    delta_T = [p['indoor_c'] - outdoor_mean for p in event]

    # require monotonically decreasing ΔT (allowing one non-monotone step)
    non_monotone = sum(1 for i in range(1, len(delta_T))
                       if delta_T[i] >= delta_T[i - 1])
    if non_monotone > 1:
        return None

    # log-transform: only use points where ΔT > 1°C
    xs, ys = [], []
    for i, dT in enumerate(delta_T):
        if dT > 1.0:
            xs.append(i * dt_hours)
            ys.append(math.log(dT))

    if len(xs) < 4:
        return None

    # OLS: y = a + b*x, where b = -1/τ
    n    = len(xs)
    sx   = sum(xs)
    sy   = sum(ys)
    sxx  = sum(x * x for x in xs)
    sxy  = sum(x * y for x, y in zip(xs, ys))

    denom = n * sxx - sx * sx
    if abs(denom) < 1e-12:
        return None

    b = (n * sxy - sx * sy) / denom   # slope = -1/τ
    a = (sy - b * sx) / n              # intercept = ln(A)

    if b >= 0:
        return None   # positive slope means temperature rising — not a decay

    tau_hours = -1.0 / b

    # R² for quality assessment
    y_mean = sy / n
    ss_tot = sum((y - y_mean) ** 2 for y in ys)
    ss_res = sum((y - (a + b * x)) ** 2 for x, y in zip(xs, ys))
    r_sq   = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

    return {
        'tau_hours':          round(tau_hours, 2),
        'r_squared':          round(r_sq, 4),
        'n_points':           n,
        'delta_T_start_c':    round(delta_T[0], 2),
        'outdoor_mean_c':     round(outdoor_mean, 2),
        'fit_quality':        'good' if r_sq >= 0.95 else 'acceptable' if r_sq >= 0.85 else 'poor',
        'event_duration_h':   len(event) * dt_hours,
    }
```

Only accept fits with R² ≥ 0.85. Discard fits from events shorter than 4 periods or with ΔT_start < 3°C — the signal-to-noise ratio is insufficient.

### Step 3: Aggregate τ estimates over time

A single decay event gives a noisy τ estimate. Build a robust household estimate from multiple events.

```python
def aggregate_tau(event_fits: list[dict],
                  min_events: int = 5) -> dict | None:
    """
    event_fits: list of fit results from fit_tau.
    Weight by R² × n_points — better-quality, longer events get more weight.
    """
    good_fits = [f for f in event_fits
                 if f is not None and f['fit_quality'] in ('good', 'acceptable')]

    if len(good_fits) < min_events:
        return None

    weights = [f['r_squared'] * f['n_points'] for f in good_fits]
    total_w = sum(weights)
    tau_w   = sum(f['tau_hours'] * w for f, w in zip(good_fits, weights)) / total_w

    # weighted standard deviation
    var_w  = sum(w * (f['tau_hours'] - tau_w) ** 2
                 for f, w in zip(good_fits, weights)) / total_w
    std_w  = var_w ** 0.5

    return {
        'tau_hours':            round(tau_w, 2),
        'tau_std_hours':        round(std_w, 2),
        'tau_95ci_low':         round(tau_w - 1.96 * std_w, 2),
        'tau_95ci_high':        round(tau_w + 1.96 * std_w, 2),
        'n_events':             len(good_fits),
        'fit_quality_breakdown': {
            'good':       sum(1 for f in good_fits if f['fit_quality'] == 'good'),
            'acceptable': sum(1 for f in good_fits if f['fit_quality'] == 'acceptable'),
        },
    }
```

### Step 4: Calculate HLC

```python
# Thermal capacitance lookup by property type and build era (Wh/K per m² floor area)
# Based on ISO 13786 dynamic thermal characterisation, UK calibration from BEIS NEED
CAPACITANCE_WH_PER_K_PER_M2 = {
    ('detached',  'pre_1945'):  240,
    ('detached',  '1945_1980'): 190,
    ('detached',  'post_1980'): 155,
    ('semi',      'pre_1945'):  220,
    ('semi',      '1945_1980'): 175,
    ('semi',      'post_1980'): 145,
    ('terraced',  'pre_1945'):  210,
    ('terraced',  '1945_1980'): 165,
    ('terraced',  'post_1980'): 135,
    ('flat',      'pre_1945'):  170,
    ('flat',      '1945_1980'): 140,
    ('flat',      'post_1980'): 115,
}

def calculate_hlc(tau_result: dict,
                   floor_area_m2: float,
                   property_type: str,
                   build_era: str) -> dict:
    """
    Returns HLC in W/K with confidence interval.
    HLC = C / τ, where C = specific_capacitance × floor_area
    """
    key = (property_type, build_era)
    c_wh_per_k_m2 = CAPACITANCE_WH_PER_K_PER_M2.get(key, 170)  # fallback: mid-range
    C_wh_per_k    = c_wh_per_k_m2 * floor_area_m2

    tau_h     = tau_result['tau_hours']
    tau_low   = tau_result['tau_95ci_low']
    tau_high  = tau_result['tau_95ci_high']

    hlc       = C_wh_per_k / tau_h            # W/K (Wh/K ÷ hours)
    hlc_low   = C_wh_per_k / tau_high         # lower HLC = better insulation
    hlc_high  = C_wh_per_k / tau_low          # higher HLC = worse insulation

    # Heat loss rate per degree (W/K) per m² for benchmarking
    hlc_per_m2 = hlc / floor_area_m2

    return {
        'hlc_w_per_k':         round(hlc, 1),
        'hlc_95ci_low':        round(hlc_low, 1),
        'hlc_95ci_high':       round(hlc_high, 1),
        'hlc_per_m2':          round(hlc_per_m2, 2),
        'capacitance_wh_per_k': round(C_wh_per_k, 0),
        'assumed_c_source':    'property_type_lookup',
    }
```

The biggest source of uncertainty in HLC is the assumed thermal capacitance C. The capacitance lookup introduces ±20% uncertainty for most properties. This is acceptable for EPC band-level comparison but not for fine-grained auditing. Treat HLC results as indicative within a ±25% confidence band unless C is measured directly (possible but requires a controlled heating experiment).

### Step 5: Seasonal trend monitoring

Run the aggregation on a rolling 8-week window and track τ over time.

```python
def seasonal_tau_trend(weekly_tau: list[tuple[date, float]]) -> dict:
    """
    weekly_tau: [(week_start_date, tau_hours)] chronological.
    Detects if insulation quality is degrading (τ decreasing over time).
    """
    if len(weekly_tau) < 8:
        return {'status': 'insufficient_data'}

    # simple linear regression of tau vs week index
    n   = len(weekly_tau)
    xs  = list(range(n))
    ys  = [t[1] for t in weekly_tau]
    sx  = sum(xs);  sy  = sum(ys)
    sxx = sum(x*x for x in xs)
    sxy = sum(x*y for x, y in zip(xs, ys))
    denom = n * sxx - sx * sx

    if abs(denom) < 1e-9:
        return {'trend': 'flat', 'slope_hours_per_week': 0.0}

    slope = (n * sxy - sx * sy) / denom   # hours per week

    # A negative slope means τ is shrinking → degrading insulation
    pct_change_over_period = slope * n / ys[0] * 100

    return {
        'slope_hours_per_week':      round(slope, 3),
        'pct_change_over_period':    round(pct_change_over_period, 1),
        'trend':                     ('degrading' if slope < -0.05
                                      else 'improving' if slope > 0.05 else 'stable'),
        'alert': slope < -0.1 and pct_change_over_period < -10,
    }
```

---

## 5. Service #13a — Measured vs Modelled Performance Gap

### Estimating SAP HTC from EPC data

UK EPC data is publicly available via the MHCLG EPC register API (requires registration). The relevant fields are:

```
energy_consumption_current   # kWh/m²/year
environment_impact_current   # CO2 kg/m²/year
heat_loss_floor              # area-weighted U-value of floor
heat_loss_walls              # area-weighted U-value of walls
heat_loss_roof               # area-weighted U-value of roof
heat_loss_windows            # area-weighted U-value of windows
number_of_habitable_rooms
total_floor_area
construction_age_band
property_type
```

Reverse-engineer SAP HTC from EPC energy consumption data:

```python
HEATING_SEASON_HDD_UK = 2100   # approximate annual UK degree-days (base 15.5°C, England average)
BOILER_EFFICIENCY     = 0.89   # modern condensing
HOURS_PER_YEAR        = 8760

def estimate_sap_htc(epc_energy_kwh_per_m2_year: float,
                      floor_area_m2: float,
                      base_load_kwh_per_day: float = 3.5) -> dict:
    """
    Estimates SAP HTC by inverting the space heating energy calculation.
    epc_energy_kwh_per_m2_year: from EPC register (total energy, not just heating)
    base_load_kwh_per_day: non-heating gas (hot water + cooking), default 3.5 kWh/day
    """
    total_annual_kwh     = epc_energy_kwh_per_m2_year * floor_area_m2
    base_load_annual_kwh = base_load_kwh_per_day * 365
    heating_kwh_year     = max(total_annual_kwh - base_load_annual_kwh, 0.0)

    # SAP models: heating_kwh = HTC × HDD × 24 / boiler_efficiency / 1000
    # Solving for HTC:
    if HEATING_SEASON_HDD_UK > 0:
        htc_w_per_k = (heating_kwh_year * BOILER_EFFICIENCY * 1000
                       / (HEATING_SEASON_HDD_UK * 24))
    else:
        htc_w_per_k = None

    return {
        'sap_htc_w_per_k':       round(htc_w_per_k, 1) if htc_w_per_k else None,
        'sap_heating_kwh_year':  round(heating_kwh_year, 0),
        'estimation_method':     'epc_register_inversion',
    }
```

This is an approximation. Where the full EPC lodgement data is available (wall U-values, floor area, etc.), compute HTC directly from the fabric heat loss components. Use the inverted approach as the fallback when full SAP data is not accessible.

### Computing the performance gap

```python
def performance_gap(measured_hlc: dict, sap_htc_w_per_k: float) -> dict:
    """
    Compares measured HLC against SAP-predicted HTC.
    Both in W/K; they are conceptually equivalent for this comparison.
    """
    hlc   = measured_hlc['hlc_w_per_k']
    gap   = hlc - sap_htc_w_per_k
    gap_pct = gap / sap_htc_w_per_k * 100

    # Confidence interval on the gap
    gap_low  = measured_hlc['hlc_95ci_low']  - sap_htc_w_per_k
    gap_high = measured_hlc['hlc_95ci_high'] - sap_htc_w_per_k

    # Classify gap magnitude
    if gap_pct < -10:
        interpretation = 'performs_better_than_epc'
    elif gap_pct < 10:
        interpretation = 'consistent_with_epc'
    elif gap_pct < 30:
        interpretation = 'moderate_performance_gap'
    elif gap_pct < 60:
        interpretation = 'significant_performance_gap'
    else:
        interpretation = 'severe_performance_gap'

    # Annual cost of the gap
    # Extra heating cost = gap_W_per_K × annual_HDD × 24h / boiler_efficiency / 1000 × gas_rate
    extra_kwh_year = max(gap, 0) * HEATING_SEASON_HDD_UK * 24 / 1000
    # (caller multiplies by gas_rate_p_per_kwh / 100 for GBP)

    return {
        'measured_hlc_w_per_k':  hlc,
        'sap_htc_w_per_k':       round(sap_htc_w_per_k, 1),
        'gap_w_per_k':           round(gap, 1),
        'gap_pct':               round(gap_pct, 1),
        'gap_95ci_low_w_per_k':  round(gap_low, 1),
        'gap_95ci_high_w_per_k': round(gap_high, 1),
        'interpretation':        interpretation,
        'extra_heating_kwh_year':round(extra_kwh_year, 0),
    }
```

### Identifying gap drivers

The performance gap has three main causes, which can be partially distinguished from data:

**1. Fabric infiltration** (air leakage above SAP assumption)
Signature: gap is larger on windy days. Test by comparing τ estimates on high-wind vs calm days from the same temperature range.

**2. Thermal bridging underestimated**
Signature: gap exists uniformly across all weather conditions. No wind correlation. Particularly common in pre-1980 cavity wall properties where the SAP linear thermal bridging (ψ) values are modelled from defaults.

**3. Occupant-driven heat loss** (window opening, door habits)
Signature: gap is larger during daytime / occupied periods. Free cooling events yield different τ values when occupants are home vs when they are away (if Tier 3 data is available).

```python
def correlate_gap_with_wind(event_fits: list[dict],
                             event_winds: list[float]) -> dict:
    """
    event_fits: list of tau results
    event_winds: mean wind speed (m/s) during each event
    Returns correlation and likely gap driver.
    """
    if len(event_fits) < 10:
        return {'status': 'insufficient_events'}

    taus  = [f['tau_hours'] for f in event_fits if f is not None]
    winds = [w for f, w in zip(event_fits, event_winds) if f is not None]

    n   = len(taus)
    if n < 10:
        return {'status': 'insufficient_events'}

    # Pearson correlation between tau and wind speed
    t_mean = sum(taus)  / n
    w_mean = sum(winds) / n
    num    = sum((t - t_mean) * (w - w_mean) for t, w in zip(taus, winds))
    den_t  = sum((t - t_mean) ** 2 for t in taus) ** 0.5
    den_w  = sum((w - w_mean) ** 2 for w in winds) ** 0.5
    corr   = num / (den_t * den_w) if den_t * den_w > 0 else 0.0

    # Negative correlation: more wind → shorter τ → infiltration driver
    driver = ('infiltration_likely'   if corr < -0.40 else
              'thermal_bridging_likely' if abs(corr) < 0.20 else
              'mixed_or_occupant_driven')

    return {
        'wind_tau_correlation': round(corr, 3),
        'gap_driver':           driver,
        'n_events_analysed':    n,
    }
```

---

## 6. Service #13b — Continuous / Dynamic EPC

### EPC band boundaries

Map the measured HLC/m² to an EPC band using the same boundaries as SAP, translated to the heat loss coefficient per unit area.

SAP defines bands via the Energy Efficiency Rating (EER) score. The EER does not map linearly to HLC because it includes other factors (heating system efficiency, lighting). However, for a household with a known gas boiler, a monotonic mapping exists:

```python
# Approximate HLC/m² (W/K/m²) at EPC band boundaries
# For a typical 3-bed semi with a condensing gas boiler
# Derived by inverting the SAP energy equations at band boundaries
EPC_BANDS_HLC_PER_M2 = [
    ('A', 0.0,  0.70),   # EER 92–100
    ('B', 0.70, 0.95),   # EER 81–91
    ('C', 0.95, 1.30),   # EER 69–80
    ('D', 1.30, 1.75),   # EER 55–68
    ('E', 1.75, 2.35),   # EER 39–54
    ('F', 2.35, 3.20),   # EER 21–38
    ('G', 3.20, 99.9),   # EER 1–20
]

def hlc_to_epc_band(hlc_per_m2: float) -> dict:
    for band, lo, hi in EPC_BANDS_HLC_PER_M2:
        if lo <= hlc_per_m2 < hi:
            mid_band_hlc = (lo + hi) / 2
            position_in_band = (hlc_per_m2 - lo) / (hi - lo)   # 0 = top of band, 1 = bottom
            return {
                'band':             band,
                'position_in_band': round(position_in_band, 2),
                'description':      ('towards top of band' if position_in_band < 0.33
                                     else 'mid-band' if position_in_band < 0.67
                                     else 'towards bottom of band'),
            }
    return {'band': 'G', 'position_in_band': 1.0}
```

These thresholds are property-type specific in full SAP. The values above are calibrated for a 3-bed semi-detached with a condensing gas boiler. Adjust the lookup table for different property archetypes.

### Rolling EPC update

Recompute the dynamic EPC band each month using the prior 8 weeks of decay events.

```python
def rolling_epc(monthly_tau_results: list[tuple[date, dict]],
                floor_area_m2: float,
                property_type: str,
                build_era: str) -> list[dict]:
    """
    monthly_tau_results: [(month_start_date, tau_aggregate_result)]
    Returns the dynamic EPC time series.
    """
    series = []
    for month_date, tau_agg in monthly_tau_results:
        if tau_agg is None:
            series.append({'month': month_date.isoformat(), 'band': None,
                           'status': 'insufficient_decay_events'})
            continue

        hlc_result = calculate_hlc(tau_agg, floor_area_m2, property_type, build_era)
        band_result = hlc_to_epc_band(hlc_result['hlc_per_m2'])

        series.append({
            'month':          month_date.isoformat(),
            'tau_hours':      tau_agg['tau_hours'],
            'hlc_w_per_k':    hlc_result['hlc_w_per_k'],
            'hlc_per_m2':     hlc_result['hlc_per_m2'],
            'band':           band_result['band'],
            'n_events':       tau_agg['n_events'],
        })

    return series
```

### Band change alert

Flag when the measured band shifts by one or more letters compared to the prior 3-month average. This is the signal that a significant change in fabric performance has occurred (retrofit improvement or fault-driven degradation).

```python
def detect_band_change(series: list[dict], lookback_months: int = 3) -> dict | None:
    valid = [s for s in series if s.get('band')]
    if len(valid) < lookback_months + 1:
        return None

    recent  = valid[-1]['band']
    prior   = valid[-(lookback_months + 1)]['band']
    band_order = 'ABCDEFG'

    change = band_order.index(recent) - band_order.index(prior)
    if change == 0:
        return None

    return {
        'prior_band':     prior,
        'current_band':   recent,
        'change_letters': change,
        'direction':      'improvement' if change < 0 else 'degradation',
        'alert':          abs(change) >= 1,
    }
```

---

## 7. Service #13c — Retrofit Impact Verification

### Before/after methodology

A retrofit event (insulation, window replacement, heat pump, loft boarding) should increase τ and decrease HLC. Verify this by comparing the τ distributions from the pre-retrofit and post-retrofit periods.

Minimum data requirements:
- Pre-retrofit: at least 20 qualifying decay events (typically one heating season)
- Post-retrofit: at least 10 qualifying decay events before declaring a result (allow 6–8 weeks post-installation for materials to settle and thermal performance to stabilise)

```python
def retrofit_verification(pre_fits: list[dict],
                           post_fits: list[dict],
                           retrofit_date: date) -> dict:
    """
    pre_fits:  tau fit results from before retrofit_date
    post_fits: tau fit results from after retrofit_date + 6 weeks settling time
    """
    if len(pre_fits) < 10 or len(post_fits) < 6:
        return {'status': 'insufficient_data',
                'pre_events': len(pre_fits),
                'post_events': len(post_fits)}

    pre_taus  = [f['tau_hours'] for f in pre_fits  if f and f['fit_quality'] != 'poor']
    post_taus = [f['tau_hours'] for f in post_fits if f and f['fit_quality'] != 'poor']

    pre_mean  = sum(pre_taus)  / len(pre_taus)
    post_mean = sum(post_taus) / len(post_taus)

    improvement_pct = (post_mean - pre_mean) / pre_mean * 100

    # Welch's t-test for unequal sample sizes and variances
    pre_var   = sum((t - pre_mean)  ** 2 for t in pre_taus)  / max(len(pre_taus)  - 1, 1)
    post_var  = sum((t - post_mean) ** 2 for t in post_taus) / max(len(post_taus) - 1, 1)
    se        = (pre_var / len(pre_taus) + post_var / len(post_taus)) ** 0.5
    t_stat    = (post_mean - pre_mean) / se if se > 0 else 0.0

    # Approximate p-value for |t| > 2.0 with df > 15: p < 0.05
    statistically_significant = abs(t_stat) > 2.0 and len(pre_taus) + len(post_taus) > 20

    return {
        'retrofit_date':         retrofit_date.isoformat(),
        'pre_tau_mean_hours':    round(pre_mean, 2),
        'post_tau_mean_hours':   round(post_mean, 2),
        'improvement_pct':       round(improvement_pct, 1),
        'tau_change_hours':      round(post_mean - pre_mean, 2),
        't_statistic':           round(t_stat, 2),
        'statistically_significant': statistically_significant,
        'pre_event_count':       len(pre_taus),
        'post_event_count':      len(post_taus),
        'verdict':               _retrofit_verdict(improvement_pct, statistically_significant),
    }

def _retrofit_verdict(improvement_pct: float, significant: bool) -> str:
    if not significant:
        return 'no_detectable_improvement_yet'
    if improvement_pct >= 20:
        return 'significant_improvement_verified'
    if improvement_pct >= 8:
        return 'moderate_improvement_detected'
    if improvement_pct >= 0:
        return 'marginal_improvement_only'
    return 'no_improvement_or_degradation'
```

### Claimed vs measured improvement

Retrofits are sold with predicted improvement claims. Compare the measured τ improvement against the installer's predicted fabric improvement:

```python
def claimed_vs_measured(claimed_hlc_reduction_pct: float,
                         measured_tau_improvement_pct: float,
                         pre_hlc: dict,
                         post_hlc: dict) -> dict:
    """
    claimed_hlc_reduction_pct: installer's predicted HLC reduction (e.g. 25 for 25%)
    measured_tau_improvement_pct: from retrofit_verification output
    """
    # τ improvement ≈ HLC improvement if C is constant before/after
    # (C changes slightly if e.g. solid wall insulation adds mass, but this is second-order)
    gap_pct = measured_tau_improvement_pct - claimed_hlc_reduction_pct

    return {
        'claimed_reduction_pct':  claimed_hlc_reduction_pct,
        'measured_improvement_pct': measured_tau_improvement_pct,
        'delivery_gap_pct':       round(gap_pct, 1),
        'pre_hlc_w_per_k':        pre_hlc['hlc_w_per_k'],
        'post_hlc_w_per_k':       post_hlc['hlc_w_per_k'],
        'delivered_as_claimed':   gap_pct >= -5,   # within 5 percentage points
        'shortfall_kwh_year':     round(
            max(-gap_pct / 100 * pre_hlc['hlc_w_per_k'], 0)
            * HEATING_SEASON_HDD_UK * 24 / 1000, 0),
    }
```

### ECO4 and grant scheme compliance

The ECO4 scheme requires third-party verification that installed measures delivered their claimed improvement. The retrofit_verification output can serve as that evidence, provided:

1. The sensor was installed at least one full heating season before the retrofit
2. At least 20 pre-retrofit decay events were captured
3. Post-retrofit data collection continues for at least 3 months before issuing a verification report

Document all these requirements in the evidence package. An assessor reviewing the package should be able to reproduce the τ calculation from the raw sensor data.

---

## 8. Service #13d — Green Mortgage and Valuation Support

### Evidence package structure

Green mortgage lenders (Halifax, Nationwide, NatWest Green Mortgage) currently rely on the EPC certificate alone. The measured HLC provides supplementary evidence of genuine fabric performance.

Generate a structured evidence package for a given household at a point in time:

```python
def generate_evidence_package(household_id: str,
                               as_of_date: date,
                               tau_history: list[tuple[date, dict]],
                               hlc_current: dict,
                               epc_band_current: dict,
                               epc_band_certificate: str,
                               performance_gap: dict,
                               retrofit_verifications: list[dict]) -> dict:
    return {
        'package_version':      '1.0',
        'generated_at':         as_of_date.isoformat(),
        'household_id':         household_id,

        'sensor_data_summary': {
            'first_reading_date':  tau_history[0][0].isoformat() if tau_history else None,
            'total_decay_events':  sum(t[1]['n_events'] for _, t in tau_history if t),
            'data_quality':        'verified' if len(tau_history) >= 6 else 'provisional',
        },

        'measured_performance': {
            'tau_hours':          hlc_current['tau_hours'] if 'tau_hours' in hlc_current else None,
            'hlc_w_per_k':        hlc_current['hlc_w_per_k'],
            'hlc_95ci_low':       hlc_current['hlc_95ci_low'],
            'hlc_95ci_high':      hlc_current['hlc_95ci_high'],
            'measured_epc_band':  epc_band_current['band'],
        },

        'certificate_comparison': {
            'certificate_band':   epc_band_certificate,
            'measured_band':      epc_band_current['band'],
            'performance_gap_pct': performance_gap['gap_pct'],
            'consistent':         abs(performance_gap['gap_pct']) < 20,
        },

        'retrofit_evidence':    retrofit_verifications,

        'methodology_notes': [
            'HLC estimated from overnight free cooling events using Newton\'s Law of Cooling.',
            'Thermal capacitance estimated from property type and construction era lookup (ISO 13786).',
            'Outdoor temperature from Open-Meteo reanalysis data at property postcode centroid.',
            'Confidence interval reflects statistical variation across decay events; '
            'does not include uncertainty in thermal capacitance assumption (~±20%).',
        ],
    }
```

### Band consistency check

If the measured band is worse than the certificate band (e.g. measured D, certificate C), include this explicitly in the mortgage application narrative. If measured band is better, highlight it as evidence of actual performance exceeding the certificate.

```python
def mortgage_narrative(gap: dict, measured_band: str, cert_band: str) -> str:
    band_order = 'ABCDEFG'
    cert_idx   = band_order.index(cert_band)
    meas_idx   = band_order.index(measured_band)

    if meas_idx < cert_idx:
        return (f"The property's measured thermal performance (band {measured_band}) "
                f"exceeds the EPC certificate rating (band {cert_band}), providing "
                f"stronger evidence of fabric quality than the certificate alone.")
    elif meas_idx == cert_idx:
        return (f"The property's measured thermal performance (band {measured_band}) "
                f"is consistent with the EPC certificate rating, confirming the "
                f"certificate reflects actual building behaviour.")
    else:
        return (f"The property's measured thermal performance (band {measured_band}) "
                f"is below the EPC certificate rating (band {cert_band}). "
                f"The performance gap of {gap['gap_pct']:.0f}% may indicate "
                f"installation defects or modelling assumptions in the original SAP assessment "
                f"that do not reflect actual building behaviour.")
```

---

## 9. Service #13e — National Housing Stock Carbon Accuracy

### Aggregation methodology

At scale, the per-household HLC measurements can improve national carbon accounting for the residential sector. BEIS currently relies on SAP-modelled HTC values. Measured HLC data at scale provides a calibration dataset.

```python
def national_stock_contribution(household_records: list[dict]) -> dict:
    """
    household_records: list of {property_type, build_era, floor_area_m2,
                                 hlc_w_per_k, sap_htc_w_per_k, gap_pct}
    Aggregates to produce population-level statistics.
    """
    from collections import defaultdict

    by_segment: dict[tuple, list] = defaultdict(list)
    for rec in household_records:
        segment = (rec['property_type'], rec['build_era'])
        by_segment[segment].append(rec['gap_pct'])

    segment_stats = {}
    for segment, gaps in by_segment.items():
        sorted_gaps = sorted(gaps)
        n = len(sorted_gaps)
        segment_stats[str(segment)] = {
            'n_properties':     n,
            'median_gap_pct':   sorted_gaps[n // 2],
            'p25_gap_pct':      sorted_gaps[n // 4],
            'p75_gap_pct':      sorted_gaps[int(n * 0.75)],
        }

    # Properties with gap > 0 are underperforming their EPC
    underperforming = sum(1 for r in household_records if r['gap_pct'] > 10)

    return {
        'total_households_measured': len(household_records),
        'pct_underperforming_epc':  round(underperforming / len(household_records) * 100, 1),
        'by_segment':               segment_stats,
    }
```

### Privacy and anonymisation

Aggregated outputs must never enable identification of individual households. Apply k-anonymity: no segment cell in the output may contain fewer than k=10 households. Suppress and aggregate upward any cell below this threshold.

```python
K_ANONYMITY_MIN = 10

def apply_k_anonymity(segment_stats: dict) -> dict:
    suppressed = {k: v for k, v in segment_stats.items()
                  if v['n_properties'] >= K_ANONYMITY_MIN}
    suppressed_count = sum(v['n_properties'] for k, v in segment_stats.items()
                           if v['n_properties'] < K_ANONYMITY_MIN)

    if suppressed_count > 0:
        suppressed['other_suppressed'] = {
            'n_properties': suppressed_count,
            'note': f'Cells with fewer than {K_ANONYMITY_MIN} households suppressed.'
        }

    return suppressed
```

---

## 10. Service #14 — Comfort vs Cost Trade-Off Reporting

### Comfort envelope definition

WHO and CIBSE define the comfort temperature band for sedentary activity as 18–22°C. Apply a time-weighted comfort score that accounts for when the property is occupied:

```python
COMFORT_LOWER_C = 18.0   # below this: too cold for sedentary comfort
COMFORT_UPPER_C = 22.0   # above this: too warm (energy waste in winter context)
HEALTH_RISK_C   = 16.0   # below this: health risk for elderly or vulnerable occupants

def period_comfort_score(indoor_temp_c: float) -> float:
    """Returns 0.0 (uncomfortable) to 1.0 (fully comfortable)."""
    if indoor_temp_c < HEALTH_RISK_C:
        return 0.0
    elif indoor_temp_c < COMFORT_LOWER_C:
        # linear ramp from 0 at health risk to 1 at lower comfort bound
        return (indoor_temp_c - HEALTH_RISK_C) / (COMFORT_LOWER_C - HEALTH_RISK_C)
    elif indoor_temp_c <= COMFORT_UPPER_C:
        return 1.0
    else:
        # above upper comfort: still comfortable, but wasteful; score does not drop
        # (uncomfortably hot is unusual in UK residential heating context)
        return 1.0
```

### Weekly comfort report

```python
def weekly_comfort_report(periods: list[dict],
                           occupancy: dict[tuple[date, int], str],
                           tariff: object,   # from service #1
                           gas_rate_p: float) -> dict:
    """
    periods: aligned period records with indoor_c, elec_kwh, gas_kwh.
    occupancy: {(date, period_index): 'OCCUPIED'|'VACANT'|'UNKNOWN'}
    """
    occupied_comfort_scores  = []
    vacant_cost_p            = 0.0
    occupied_cost_p          = 0.0
    total_cost_p             = 0.0
    cold_occupied_periods    = []   # periods where occupied + below comfort
    health_risk_periods      = []

    for p in periods:
        if not p.get('complete'):
            continue

        d, period    = p['date'], p['period']
        occ          = occupancy.get((d, period), 'UNKNOWN')
        indoor_temp  = p['indoor_c']
        elec_kwh     = p.get('elec_kwh', 0.0)
        gas_kwh      = p.get('gas_kwh', 0.0)

        elec_rate_p  = rate_for_period(tariff, d, period)
        period_cost_p = elec_kwh * elec_rate_p + gas_kwh * gas_rate_p
        total_cost_p += period_cost_p

        comfort = period_comfort_score(indoor_temp)

        if occ == 'OCCUPIED':
            occupied_comfort_scores.append(comfort)
            occupied_cost_p += period_cost_p
            if indoor_temp < COMFORT_LOWER_C:
                cold_occupied_periods.append({'date': d, 'period': period,
                                               'temp_c': indoor_temp})
            if indoor_temp < HEALTH_RISK_C:
                health_risk_periods.append({'date': d, 'period': period,
                                             'temp_c': indoor_temp})

        elif occ == 'VACANT':
            vacant_cost_p += period_cost_p

    n_occ = len(occupied_comfort_scores)
    mean_comfort = sum(occupied_comfort_scores) / n_occ if n_occ > 0 else None
    pct_in_comfort_zone = (sum(1 for s in occupied_comfort_scores if s >= 1.0)
                           / n_occ * 100) if n_occ > 0 else None

    return {
        'total_cost_gbp':              round(total_cost_p / 100, 2),
        'occupied_cost_gbp':           round(occupied_cost_p / 100, 2),
        'vacant_cost_gbp':             round(vacant_cost_p / 100, 2),
        'vacant_cost_pct':             round(vacant_cost_p / total_cost_p * 100, 1) if total_cost_p > 0 else 0,
        'occupied_periods':            n_occ,
        'mean_comfort_score':          round(mean_comfort, 3) if mean_comfort is not None else None,
        'pct_occupied_in_comfort':     round(pct_in_comfort_zone, 1) if pct_in_comfort_zone is not None else None,
        'cold_occupied_period_count':  len(cold_occupied_periods),
        'health_risk_period_count':    len(health_risk_periods),
        'health_risk_alert':           len(health_risk_periods) > 0,
        'cold_occupied_periods':       cold_occupied_periods[:5],   # sample, not exhaustive
    }
```

### Trade-off quadrant analysis

Classify the household's weekly pattern into one of four trade-off quadrants:

```python
def comfort_cost_quadrant(weekly_report: dict,
                           peer_comfort_mean: float,
                           peer_cost_mean_gbp: float) -> dict:
    """
    Places the household in one of four quadrants relative to peer medians.
    """
    comfort = weekly_report['pct_occupied_in_comfort']
    cost    = weekly_report['total_cost_gbp']

    above_peer_comfort = comfort > peer_comfort_mean
    above_peer_cost    = cost    > peer_cost_mean_gbp

    if above_peer_comfort and not above_peer_cost:
        quadrant    = 'efficient_and_comfortable'
        description = 'Above-average comfort at below-average cost. Well-optimised.'
        action      = None
    elif above_peer_comfort and above_peer_cost:
        quadrant    = 'comfortable_but_expensive'
        description = 'Above-average comfort but above-average cost. Check for vacant-period heating waste.'
        action      = 'Review heating schedule — check if heating is running when no one is home.'
    elif not above_peer_comfort and not above_peer_cost:
        quadrant    = 'cold_and_cheap'
        description = 'Below-average comfort at below-average cost. Home may be under-heated when occupied.'
        action      = 'Consider raising thermostat setpoint during occupied periods.'
    else:
        quadrant    = 'cold_and_expensive'
        description = 'Below-average comfort despite above-average cost. Likely a heating efficiency problem.'
        action      = 'Check boiler performance and thermostat calibration. See service #5 boiler trend report.'

    return {
        'quadrant':           quadrant,
        'description':        description,
        'recommended_action': action,
        'comfort_score_pct':  comfort,
        'weekly_cost_gbp':    cost,
        'peer_comfort_pct':   peer_comfort_mean,
        'peer_cost_gbp':      peer_cost_mean_gbp,
    }
```

### Heating schedule efficiency

Identify the fraction of heating energy consumed while the property is vacant. This is the single most actionable metric for reducing cost without reducing comfort.

```python
def heating_schedule_efficiency(weekly_report: dict) -> dict:
    vacant_pct = weekly_report['vacant_cost_pct']

    if vacant_pct > 30:
        efficiency = 'poor'
        message    = (f"{vacant_pct:.0f}% of your energy cost is spent heating an empty home. "
                      f"A programmable or smart thermostat schedule could recover most of this.")
    elif vacant_pct > 15:
        efficiency = 'moderate'
        message    = (f"{vacant_pct:.0f}% of your energy cost occurs when the home is empty. "
                      f"Tightening your heating schedule could save £"
                      f"{weekly_report['vacant_cost_gbp'] * 52 * 0.4:.0f}/year.")
    else:
        efficiency = 'good'
        message    = (f"Only {vacant_pct:.0f}% of energy cost occurs when the home is empty. "
                      f"Your heating schedule is well-matched to occupancy.")

    return {
        'vacant_heating_pct': vacant_pct,
        'efficiency_rating':  efficiency,
        'message':            message,
        'annual_vacant_cost_estimate_gbp': round(weekly_report['vacant_cost_gbp'] * 52, 0),
    }
```

---

## 11. Implementation Order and Dependencies

```
Tier 2 (weather API)          — required before any HLC calculation
Service #13 (τ + HLC)         — build first; everything else in Tier 4 depends on it
Service #13b (dynamic EPC)    — depends on #13; can run as soon as 5 decay events are available
Service #13a (gap analysis)   — depends on #13 + EPC register API lookup
Service #13c (retrofit)       — depends on #13 pre and post; activate on user-declared retrofit date
Service #13d (mortgage)       — depends on #13a + #13c; generates report on demand
Service #13e (national stock) — depends on aggregated #13 data; runs server-side across all households
Service #14  (comfort/cost)   — depends on indoor temp + tariff from service #1; benefits from Tier 3 occupancy
```

Service #14 is the only Tier 4 service that can deliver immediate value from the first week of sensor data. Begin generating weekly comfort reports immediately upon sensor installation. Services #13 and its sub-services require a full heating season to establish the baseline τ.

---

## 12. Minimum Data Requirements

| Service | Minimum events/time | Notes |
|---|---|---|
| #13 τ baseline | 10 qualifying decay events | Typically 4–8 weeks in heating season |
| #13 robust aggregate | 20+ decay events | Needed for 95% CI width < ±15% |
| #13a performance gap | 1 full heating season + EPC lookup | Seasonal HDD needed for SAP HTC inversion |
| #13b dynamic EPC | 5 decay events per monthly update | Gap fills with 'provisional' label |
| #13c retrofit pre | 20 decay events | One heating season minimum |
| #13c retrofit post | 10 decay events + 6-week settle | Results marked 'preliminary' until 20 events |
| #13d evidence package | #13a + #13c complete | Both must be in 'verified' status |
| #13e national aggregation | ≥ 100 households per segment | k=10 anonymity requires much larger total |
| #14 comfort report | 1 week of indoor sensor data | Works immediately; occupancy improves accuracy |

The heating season constraint (October–April) means that for a household onboarded in May, the first reliable τ estimate will not be available until January of the following year. Consider this in the product onboarding flow — set expectations explicitly and use service #14 comfort reporting to deliver immediate value during the summer waiting period.

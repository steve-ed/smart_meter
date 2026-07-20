# Tier 1 — Smart Meter Data Only: Implementation Guide

Services covered:
- **#1** Smart Tariff Matching
- **#2** Battery Size Optimisation
- **#3** Appliance Load Disaggregation
- **#4** Heat Pump Suitability Scoring

All four services require only consented half-hourly smart meter data. No additional sensors, no proprietary feeds beyond freely available weather data for service #4.

---

## 1. Data Foundations

### Half-hourly interval model

```
period_index : int        # 0–47; period 0 = 00:00–00:30, period 47 = 23:30–24:00
timestamp    : datetime   # UTC start of period
elec_kwh     : float      # electricity consumed during this half-hour (kWh)
gas_kwh      : float      # gas consumed during this half-hour (kWh), if dual-fuel
```

All four services operate on this unit. Power (Watts) is derived only when needed for physical modelling:

```python
power_w = elec_kwh * 2000   # kWh per 30-min window → average Watts during the window
```

### Canonical weekly profile

Many algorithms depend on a "typical week" — the household's expected consumption shape, free of outliers. Build this once and reuse across services.

```python
import statistics

def build_weekly_profile(readings: list[tuple[int, int, float]],
                         weeks: int = 8) -> dict[tuple[int,int], float]:
    """
    readings: [(weekday 0-6, period_index 0-47, elec_kwh)]
    Returns: {(weekday, period_index): median_kwh} over the supplied window.
    """
    slots: dict[tuple[int,int], list[float]] = {}
    for weekday, period, kwh in readings:
        key = (weekday, period)
        slots.setdefault(key, []).append(kwh)

    return {slot: statistics.median(vals) for slot, vals in slots.items()}
```

Use **median**, not mean. Half-hourly energy data is right-skewed — occasional high readings (parties, guests, EV charging) pull the mean upward and distort the profile used as the baseline for all other calculations.

### Gap handling

Smart meter reads occasionally fail. Gaps up to 2 hours (4 periods) are filled using the median value from the same (weekday, period) slot in the prior 4 weeks. Gaps longer than 2 hours are left as `None` and excluded from calculations that require continuous data (battery simulation, heat pump model). Flag data quality to the consumer-facing output.

### DST transitions

On clock-change days, the meter data provider either duplicates or skips a period. Validate that each day's period count is in {46, 48, 50}. On 46- or 50-period days, interpolate or discard the anomalous period before processing — do not include it in any rolling baseline.

---

## 2. Service #1 — Smart Tariff Matching

### Objective

Given the household's actual half-hourly consumption profile, calculate what the household would have paid on each available market tariff, rank tariffs by projected annual saving, and explain why each tariff ranks as it does.

### Tariff data model

Model each tariff as a schedule of rate bands plus a daily standing charge.

```python
@dataclass
class RateBand:
    start_period: int     # 0–47 inclusive
    end_period:   int     # 0–47 inclusive (end_period is included in this band)
    rate_p_per_kwh: float

@dataclass
class Tariff:
    name:            str
    supplier:        str
    tariff_type:     str   # 'flat' | 'two_rate' | 'tou' | 'agile' | 'tracker'
    standing_p_day:  float
    bands:           list[RateBand]
    eligibility:     list[str]   # e.g. ['smart_meter_required', 'ev_required']
    # For agile/tracker tariffs only:
    historical_rates: dict[tuple[date, int], float] | None = None
    # historical_rates: {(date, period_index): rate_p_per_kwh}
```

A flat-rate tariff has a single RateBand covering all 48 periods. A two-rate (E7) tariff has two bands. A full ToU tariff may have three or four bands. An Agile tariff has a unique rate per period per day, stored in `historical_rates`.

### Consumption profile construction

Build two representations:

**1. Annualised consumption by tariff band**

For each available tariff, map every historical half-hourly reading to the rate it would attract, then sum.

```python
def annual_cost_for_tariff(readings: list[tuple[date, int, float]],
                            tariff: Tariff) -> dict:
    """
    readings: [(date, period_index, elec_kwh)]
    Returns: {total_cost_p, unit_cost_p, standing_cost_p, days_in_sample}
    """
    unit_cost_p = 0.0
    days = len(set(r[0] for r in readings))

    for reading_date, period_idx, kwh in readings:
        if kwh is None:
            continue
        rate = rate_for_period(tariff, reading_date, period_idx)
        unit_cost_p += kwh * rate

    # scale to full year if sample < 365 days
    scale = 365 / days if days < 365 else 1.0
    unit_cost_p_annual   = unit_cost_p * scale
    standing_cost_p_annual = tariff.standing_p_day * 365

    return {
        'total_cost_gbp':    (unit_cost_p_annual + standing_cost_p_annual) / 100,
        'unit_cost_gbp':     unit_cost_p_annual / 100,
        'standing_cost_gbp': standing_cost_p_annual / 100,
        'days_in_sample':    days,
    }

def rate_for_period(tariff: Tariff, d: date, period_idx: int) -> float:
    if tariff.historical_rates:
        return tariff.historical_rates.get((d, period_idx), fallback_rate(tariff))
    for band in tariff.bands:
        if band.start_period <= period_idx <= band.end_period:
            return band.rate_p_per_kwh
    raise ValueError(f"Period {period_idx} not covered by tariff {tariff.name}")
```

**2. Consumption shape metrics**

Calculate once per household. These explain why a tariff ranks well and surface upsell opportunities.

```python
def consumption_shape(weekly_profile: dict[tuple[int,int], float]) -> dict:
    all_kwh  = sum(weekly_profile.values())
    night    = sum(v for (wd, p), v in weekly_profile.items() if  0 <= p <= 13)   # 00:00–07:00
    morning  = sum(v for (wd, p), v in weekly_profile.items() if 12 <= p <= 17)   # 06:00–09:00
    ev_peak  = sum(v for (wd, p), v in weekly_profile.items() if 32 <= p <= 41)   # 16:00–21:00
    weekend  = sum(v for (wd, p), v in weekly_profile.items() if wd >= 5)
    weekday  = sum(v for (wd, p), v in weekly_profile.items() if wd <  5)

    return {
        'night_fraction':       night   / all_kwh,   # high → favours E7, Agile overnight
        'morning_fraction':     morning / all_kwh,
        'evening_peak_fraction':ev_peak / all_kwh,   # high → penalised on Agile peak
        'weekend_kwh_ratio':    (weekend / 2) / (weekday / 5),  # >1 → home at weekends
        'annual_kwh_estimate':  all_kwh / 7 * 365,
    }
```

### Ranking and saving calculation

```python
def rank_tariffs(readings, tariffs: list[Tariff],
                 current_tariff: Tariff) -> list[dict]:
    current = annual_cost_for_tariff(readings, current_tariff)
    results = []

    for tariff in tariffs:
        cost = annual_cost_for_tariff(readings, tariff)
        saving_gbp = current['total_cost_gbp'] - cost['total_cost_gbp']
        results.append({
            'tariff':          tariff.name,
            'supplier':        tariff.supplier,
            'tariff_type':     tariff.tariff_type,
            'annual_cost_gbp': round(cost['total_cost_gbp'], 2),
            'saving_gbp':      round(saving_gbp, 2),
            'saving_pct':      round(saving_gbp / current['total_cost_gbp'] * 100, 1),
            'eligibility':     tariff.eligibility,
        })

    results.sort(key=lambda x: x['annual_cost_gbp'])
    return results
```

### Sensitivity and stability

Tariff rankings can flip based on a handful of extreme readings. Test ranking stability:

```python
def sensitivity_check(readings, tariff_a: Tariff, tariff_b: Tariff,
                       perturbation: float = 0.10) -> str:
    """
    Scale all readings ±10% and check if ranking between A and B flips.
    Returns 'stable' or 'unstable'.
    """
    def scale(r, factor):
        return [(d, p, kwh * factor) for d, p, kwh in r if kwh is not None]

    base      = annual_cost_for_tariff(readings,            tariff_a)['total_cost_gbp']
    base_b    = annual_cost_for_tariff(readings,            tariff_b)['total_cost_gbp']
    low_a     = annual_cost_for_tariff(scale(readings, 1 - perturbation), tariff_a)['total_cost_gbp']
    low_b     = annual_cost_for_tariff(scale(readings, 1 - perturbation), tariff_b)['total_cost_gbp']
    high_a    = annual_cost_for_tariff(scale(readings, 1 + perturbation), tariff_a)['total_cost_gbp']
    high_b    = annual_cost_for_tariff(scale(readings, 1 + perturbation), tariff_b)['total_cost_gbp']

    ranks = [(base < base_b), (low_a < low_b), (high_a < high_b)]
    return 'stable' if len(set(ranks)) == 1 else 'unstable'
```

Flag unstable rankings in the output — the consumer should be cautious about switching when two tariffs are close.

### Agile tariff handling

Agile (Octopus Agile and equivalents) prices change every 30 minutes and are published the day before. To model what a household would have paid historically, use the actual published half-hourly rates for each historical period. Do not assume the household would have shifted demand — model their actual fixed behaviour against the variable price. Then separately model the *potential* saving if they had shifted identified flexible loads (from service #3) to cheap slots.

### Minimum data requirement

8 weeks of half-hourly data for a reliable annual projection. Below 4 weeks, do not produce a ranking — the seasonal pattern is too incomplete. Between 4–8 weeks, produce the ranking but add a confidence caveat.

---

## 3. Service #2 — Battery Size Optimisation

### Objective

Simulate a home battery of varying capacity against the household's actual half-hourly consumption and a time-of-use tariff. Find the capacity where the projected annual saving justifies the installed cost within a reasonable payback horizon.

### Physical model

A home battery has five parameters that govern the simulation:

```python
@dataclass
class BatterySpec:
    capacity_kwh:     float   # usable capacity (not nominal — subtract DoD margin)
    max_charge_kw:    float   # maximum charge rate (inverter-limited)
    max_discharge_kw: float   # maximum discharge rate
    charge_efficiency: float  # AC→battery efficiency (typically 0.96)
    discharge_efficiency: float  # battery→AC efficiency (typically 0.96)
    # Round-trip efficiency = charge_efficiency * discharge_efficiency ≈ 0.92
```

Maximum charge/discharge rate in kW converts to a maximum per-period energy in kWh:

```python
max_charge_per_period_kwh    = max_charge_kw    * 0.5   # 30-minute window
max_discharge_per_period_kwh = max_discharge_kw * 0.5
```

### Dispatch strategy

Use a simple rule-based dispatch: charge during cheap periods, discharge during expensive periods. This is what most home battery systems actually do with basic scheduling.

```python
def is_cheap_period(period_idx: int, tariff: Tariff, cheap_threshold_p: float) -> bool:
    rate = rate_for_period(tariff, None, period_idx)
    return rate <= cheap_threshold_p

def is_expensive_period(period_idx: int, tariff: Tariff,
                         expensive_threshold_p: float) -> bool:
    rate = rate_for_period(tariff, None, period_idx)
    return rate >= expensive_threshold_p
```

For two-rate tariffs (E7), the cheap and expensive periods are fixed. For Agile, use the previous day's prices to set the cheap/expensive thresholds dynamically — the battery controller cannot see future prices.

### Core simulation

Run the simulation over the full available history (at least 365 days) for a given battery spec:

```python
def simulate_battery(readings: list[tuple[date, int, float]],
                     tariff: Tariff,
                     battery: BatterySpec,
                     cheap_threshold_p: float,
                     expensive_threshold_p: float) -> dict:

    soc = 0.0   # state of charge, kWh; start empty
    total_cost_with_battery    = 0.0
    total_cost_without_battery = 0.0
    total_charged_kwh          = 0.0
    total_discharged_kwh       = 0.0

    # group by day to handle SoC continuity across midnight
    by_day: dict[date, list[tuple[int,float]]] = {}
    for d, period, kwh in readings:
        if kwh is None:
            continue
        by_day.setdefault(d, []).append((period, kwh))

    for day in sorted(by_day):
        periods = sorted(by_day[day])   # ensure period order within day

        for period_idx, demand_kwh in periods:
            rate_p = rate_for_period(tariff, day, period_idx)

            # cost without battery
            total_cost_without_battery += demand_kwh * rate_p

            # battery dispatch decision
            grid_kwh = demand_kwh   # default: all demand from grid

            if is_cheap_period(period_idx, tariff, cheap_threshold_p):
                # charge the battery from grid if there is headroom
                headroom = battery.capacity_kwh - soc
                charge = min(headroom,
                             battery.max_charge_per_period_kwh,
                             10.0)   # sanity cap: no more than 10 kWh per period
                charge = max(charge, 0.0)
                soc          += charge * battery.charge_efficiency
                soc           = min(soc, battery.capacity_kwh)
                grid_kwh     += charge   # we draw extra from grid to charge

            elif is_expensive_period(period_idx, tariff, expensive_threshold_p):
                # discharge battery to cover demand
                available = min(soc, battery.max_discharge_per_period_kwh)
                discharge = min(available, demand_kwh)
                discharge = max(discharge, 0.0)
                soc          -= discharge
                soc           = max(soc, 0.0)
                grid_kwh     -= discharge * battery.discharge_efficiency

            grid_kwh = max(grid_kwh, 0.0)   # cannot export here; assume no feed-in
            total_cost_with_battery += grid_kwh * rate_p
            total_charged_kwh       += (grid_kwh - demand_kwh) if grid_kwh > demand_kwh else 0
            total_discharged_kwh    += (demand_kwh - grid_kwh) if demand_kwh > grid_kwh else 0

    annual_saving_p = total_cost_without_battery - total_cost_with_battery
    days_simulated  = len(by_day)

    return {
        'annual_saving_gbp':     round(annual_saving_p / 100 * 365 / days_simulated, 2),
        'annual_charged_kwh':    round(total_charged_kwh * 365 / days_simulated, 1),
        'annual_discharged_kwh': round(total_discharged_kwh * 365 / days_simulated, 1),
        'round_trip_efficiency': (battery.charge_efficiency * battery.discharge_efficiency),
    }
```

### Capacity sweep and payback curve

Run the simulation across a range of capacities to find the optimal size.

```python
CAPACITY_RANGE_KWH = [2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 13.5, 16.0]

# Installed cost benchmarks (GBP, mid-2026 UK market, including installation)
INSTALLED_COST_PER_KWH = 700   # approximate £/kWh for residential lithium systems

def payback_curve(readings, tariff, cheap_threshold_p, expensive_threshold_p) -> list[dict]:
    results = []
    for cap in CAPACITY_RANGE_KWH:
        battery = BatterySpec(
            capacity_kwh          = cap,
            max_charge_kw         = min(cap * 0.5, 3.6),   # 0.5C charge rate, capped at 3.6 kW
            max_discharge_kw      = min(cap * 0.5, 3.6),
            charge_efficiency     = 0.96,
            discharge_efficiency  = 0.96,
        )
        result = simulate_battery(readings, tariff, battery, cheap_threshold_p, expensive_threshold_p)
        installed_cost = cap * INSTALLED_COST_PER_KWH
        annual_saving  = result['annual_saving_gbp']

        payback_years = (installed_cost / annual_saving) if annual_saving > 0 else float('inf')

        results.append({
            'capacity_kwh':       cap,
            'installed_cost_gbp': installed_cost,
            'annual_saving_gbp':  annual_saving,
            'payback_years':      round(payback_years, 1),
            'npv_10yr_gbp':       round(npv(annual_saving, installed_cost, rate=0.035, years=10), 2),
        })

    return results

def npv(annual_saving: float, upfront_cost: float,
        rate: float, years: int) -> float:
    pv_savings = sum(annual_saving / (1 + rate) ** t for t in range(1, years + 1))
    return pv_savings - upfront_cost
```

The optimal capacity is typically not the largest available. Marginal returns diminish once the battery is large enough to absorb the full off-peak window. Report the capacity with the shortest payback and the capacity with the best 10-year NPV — these are often different, and the consumer should understand the trade-off.

### Solar integration

If the meter has an export MPAN (indicating solar), use import/export data to extend the model. During daylight periods where export > 0, the household is generating surplus. The battery should be charged from surplus before the grid.

```python
def dispatch_with_solar(demand_kwh, export_kwh, soc, battery, rate_p,
                         import_rate_p, export_rate_p) -> tuple[float, float]:
    """Returns (grid_import_kwh, new_soc)."""
    # solar generation = demand met locally + export
    generation = demand_kwh + export_kwh   # approximation: net metering data
    local_generation = min(generation, demand_kwh)
    surplus = generation - local_generation

    # charge battery from surplus first
    headroom = battery.capacity_kwh - soc
    charge_from_surplus = min(surplus, headroom, battery.max_charge_per_period_kwh)
    soc += charge_from_surplus * battery.charge_efficiency

    # remaining surplus would be exported (at lower export rate)
    remaining_surplus = surplus - charge_from_surplus

    # demand not met by local generation
    unmet = demand_kwh - local_generation
    discharge = min(soc, unmet, battery.max_discharge_per_period_kwh)
    soc -= discharge

    grid_import = max(unmet - discharge * battery.discharge_efficiency, 0.0)
    return grid_import, soc
```

### Battery degradation

Capacity degrades approximately 2% per year for lithium iron phosphate (LFP) chemistry, which dominates the residential UK market. Apply degradation when projecting multi-year savings:

```python
def lifetime_saving(annual_saving_year1: float, years: int = 15,
                    degradation_rate: float = 0.02,
                    discount_rate: float = 0.035) -> float:
    total = 0.0
    for year in range(1, years + 1):
        capacity_factor = (1 - degradation_rate) ** (year - 1)
        saving_this_year = annual_saving_year1 * capacity_factor
        total += saving_this_year / (1 + discount_rate) ** year
    return total
```

---

## 4. Service #3 — Appliance Load Disaggregation

### Scope and limits at 30-minute resolution

At 30-minute resolution, each period averages across 1,800 seconds. Appliances with cycle times shorter than 30 minutes (microwave, kettle, toaster) are either invisible or appear as a fractional increase spread across a period. The approach targets appliances that draw significant power for one or more complete half-hour periods:

| Appliance | Typical draw (kW) | Typical duration | kWh per period | Periods visible |
|---|---|---|---|---|
| EV charger (7 kW) | 6–7 | 2–8 hours | 3.0–3.5 | 4–16 |
| EV charger (3.6 kW) | 3.3–3.6 | 4–12 hours | 1.65–1.8 | 8–24 |
| Immersion heater | 2.8–3.2 | 30–90 min | 1.4–1.6 | 1–3 |
| Electric shower | 8–10.5 | 5–15 min | 0.7–2.6 | 1 (partial) |
| Heat pump (heating) | 1.0–3.0 | Many hours | 0.5–1.5 | Sustained |
| Washing machine | 1.0–2.5 | 45–90 min | 0.5–1.2 | 1–2 |
| Dishwasher | 1.0–2.5 | 60–120 min | 0.5–1.2 | 1–2 |
| Electric oven | 2.0–3.5 | 30–90 min | 1.0–1.75 | 1–2 |

A 30-minute period can capture a full EV charging session, a full immersion heat cycle, and a partial shower event. Washing machines and dishwashers are marginal — their signal is present but attribution confidence is lower.

### Step 1: Background profile

For each (weekday, period) slot, the background load is the long-run median — the load that would be present even without any of the target appliances.

```python
background = build_weekly_profile(readings, weeks=8)
```

For slots where the household is consistently away (VACANT occupancy if Tier 3 data is available), the background is adjusted downward. Without occupancy data, use the median — it is robust to occasional vacation weeks.

### Step 2: Residual series

```python
def compute_residual(readings: list[tuple[date, int, float]],
                     background: dict[tuple[int,int], float]) -> list[tuple[date, int, float]]:
    result = []
    for d, period, kwh in readings:
        if kwh is None:
            continue
        weekday  = d.weekday()
        expected = background.get((weekday, period), 0.0)
        residual = max(kwh - expected, 0.0)   # negative residuals = below-average, not appliance signal
        result.append((d, period, residual))
    return result
```

### Step 3: Event detection

A load event is a contiguous block of periods where the residual exceeds a detection threshold. Adjacent periods belong to the same event if there is no gap between them.

```python
DETECTION_THRESHOLD_KWH = 0.25   # residual must exceed this to start/continue an event

def detect_events(residual: list[tuple[date, int, float]]) -> list[dict]:
    events = []
    current_event = None

    for d, period, res_kwh in residual:
        if res_kwh >= DETECTION_THRESHOLD_KWH:
            if current_event is None:
                current_event = {'date': d, 'start_period': period,
                                 'end_period': period, 'periods': [res_kwh]}
            else:
                current_event['end_period'] = period
                current_event['periods'].append(res_kwh)
        else:
            if current_event is not None:
                events.append(finalise_event(current_event))
                current_event = None

    if current_event:
        events.append(finalise_event(current_event))

    return events

def finalise_event(event: dict) -> dict:
    periods  = event['periods']
    duration = len(periods)
    total_kwh = sum(periods)
    peak_kwh  = max(periods)
    return {
        'date':           event['date'],
        'start_period':   event['start_period'],
        'end_period':     event['end_period'],
        'duration_periods': duration,
        'total_kwh':      round(total_kwh, 3),
        'peak_kwh_per_period': round(peak_kwh, 3),
        'mean_kwh_per_period': round(total_kwh / duration, 3),
    }
```

### Step 4: Appliance signature matching

Each appliance has a signature defined by duration bounds, power bounds, and time-of-day affinity. Affinity is scored but not required — an immersion heater can run any time.

```python
SIGNATURES = {
    'ev_fast':    {'duration': (4, 48),  'peak_kwh': (2.5, 4.0),  'affinity_periods': range(0, 14)},
    'ev_slow':    {'duration': (8, 48),  'peak_kwh': (1.5, 2.0),  'affinity_periods': range(0, 14)},
    'immersion':  {'duration': (1,  6),  'peak_kwh': (1.3, 1.8),  'affinity_periods': list(range(0,8)) + list(range(32,40))},
    'shower':     {'duration': (1,  2),  'peak_kwh': (0.7, 2.8),  'affinity_periods': list(range(12,20)) + list(range(34,42))},
    'washing':    {'duration': (1,  4),  'peak_kwh': (0.4, 1.3),  'affinity_periods': range(14, 40)},
    'dishwasher': {'duration': (2,  5),  'peak_kwh': (0.4, 1.3),  'affinity_periods': range(36, 48)},
    'oven':       {'duration': (1,  4),  'peak_kwh': (0.9, 1.8),  'affinity_periods': range(30, 44)},
    'heat_pump':  {'duration': (6, 48),  'peak_kwh': (0.4, 1.6),  'affinity_periods': range(0, 48)},
}

def match_event(event: dict) -> list[tuple[str, float]]:
    """Returns list of (appliance_name, confidence_score 0–1)."""
    matches = []
    dur = event['duration_periods']
    peak = event['peak_kwh_per_period']
    start = event['start_period']

    for appliance, sig in SIGNATURES.items():
        score = 0.0
        components = 0

        # duration match
        if sig['duration'][0] <= dur <= sig['duration'][1]:
            score += 1.0
        elif dur < sig['duration'][0]:
            score += max(0.0, 1.0 - (sig['duration'][0] - dur) * 0.3)
        components += 1

        # peak power match
        lo, hi = sig['peak_kwh']
        if lo <= peak <= hi:
            score += 1.0
        elif peak > hi:
            score += max(0.0, 1.0 - (peak - hi) / hi * 0.5)
        elif peak < lo:
            score += max(0.0, 1.0 - (lo - peak) / lo * 0.8)
        components += 1

        # time-of-day affinity
        if start in sig['affinity_periods']:
            score += 0.5
        components += 0.5   # affinity is a weak signal, weighted down

        confidence = score / components
        if confidence >= 0.40:
            matches.append((appliance, round(confidence, 2)))

    matches.sort(key=lambda x: -x[1])
    return matches
```

### Step 5: Statistical regularisation across events

A single event match is weak evidence. Aggregate across all events in the dataset to build a probabilistic picture of which appliances are present in the household.

```python
def aggregate_appliance_evidence(events: list[dict]) -> dict[str, dict]:
    """
    For each appliance, count how many events match it (at any confidence)
    and compute the mean confidence and estimated usage frequency.
    """
    appliance_events: dict[str, list[float]] = {}

    for event in events:
        matches = match_event(event)
        for appliance, confidence in matches:
            appliance_events.setdefault(appliance, []).append(confidence)

    total_events = len(events)
    results = {}

    for appliance, confidences in appliance_events.items():
        match_count   = len(confidences)
        mean_conf     = sum(confidences) / match_count
        freq_per_week = match_count / (total_events / 7 / 48) if total_events else 0
        # Appliance is considered present in the home if:
        # - ≥ 4 matching events AND mean confidence ≥ 0.55
        likely_present = match_count >= 4 and mean_conf >= 0.55
        results[appliance] = {
            'match_count':    match_count,
            'mean_confidence': round(mean_conf, 2),
            'likely_present': likely_present,
        }

    return results
```

### Step 6: ToU cost-shift recommendations

For each detected appliance with a likely present verdict, calculate the saving from shifting typical usage to the cheapest available period on the household's current or candidate tariff.

```python
def tou_shift_saving(events: list[dict], appliance: str, tariff: Tariff,
                     confidence_threshold: float = 0.55) -> dict:
    matched = [e for e in events
               if any(a == appliance and c >= confidence_threshold
                      for a, c in match_event(e))]

    if not matched:
        return {}

    current_costs = []
    optimal_costs = []

    for event in matched:
        kwh = event['total_kwh']
        current_rate = rate_for_period(tariff, event['date'], event['start_period'])
        # optimal: cheapest period for this day
        min_rate = min(rate_for_period(tariff, event['date'], p) for p in range(48))
        current_costs.append(kwh * current_rate)
        optimal_costs.append(kwh * min_rate)

    annual_scale = 365 / (len(matched) / len(set(e['date'] for e in events)) * 365)
    saving_p = sum(c - o for c, o in zip(current_costs, optimal_costs))
    annual_saving_gbp = saving_p / 100 * annual_scale

    return {
        'appliance':          appliance,
        'events_detected':    len(matched),
        'annual_saving_gbp':  round(annual_saving_gbp, 2),
        'current_avg_rate_p': round(sum(current_costs) / sum(e['total_kwh'] for e in matched), 2),
        'optimal_avg_rate_p': round(sum(optimal_costs) / sum(e['total_kwh'] for e in matched), 2),
    }
```

### Heat pump detection edge case

A heat pump signature (sustained, moderate draw, temperature-correlated) overlaps with the background profile in winter. It raises the background rather than appearing as a residual. Detect heat pump presence separately: if winter background consumption is systematically higher than summer background by a factor that cannot be explained by lighting alone, and if the winter profile shows sustained moderate draw during morning and evening, flag likely heat pump presence.

---

## 5. Service #4 — Heat Pump Suitability Scoring

### Objective

Given a household's actual gas consumption history and historical outdoor temperature data, calculate: (a) how much of the gas use is space heating, (b) what that heating would cost on a heat pump at the household's current electricity tariff, and (c) whether installation is financially justified given the current grant regime.

### Required external data

Historical outdoor temperature data is available at no cost from:
- **Open-Meteo historical API** — sub-hourly temperature by lat/lon, 40+ year archive, free for non-commercial use
- **Met Office Hadobs** — daily degree-day data by postcode district

Map the household's postcode to a lat/lon centroid for API calls. Temperature data should be at hourly or half-hourly resolution to match the meter data.

### Step 1: Separate space heating from base gas load

The household's gas consumption has two components:

- **Base load** (B): hot water, cooking — present year-round
- **Space heating** (H): temperature-dependent — present only when the outdoor temperature falls below the heating threshold

Estimate the base load from summer consumption:

```python
def estimate_base_load(daily_gas_kwh: dict[date, float]) -> float:
    """
    Use May–September (non-heating season) daily gas consumption as the base load estimate.
    Returns: median daily base load in kWh.
    """
    summer_days = [kwh for d, kwh in daily_gas_kwh.items()
                   if 5 <= d.month <= 9]
    if len(summer_days) < 14:
        return 3.0   # fallback: 3 kWh/day is typical for hot water + cooking
    return statistics.median(summer_days)
```

For each day in the heating season (October–April), the space heating component is:

```python
def heating_kwh(total_daily_kwh: float, base_load_kwh: float) -> float:
    return max(total_daily_kwh - base_load_kwh, 0.0)
```

At the half-hourly level, the space heating fraction is distributed proportionally to the consumption shape within each day. The base load is distributed uniformly (B/48 per period); the residual heating signal follows the observed half-hourly profile.

### Step 2: Degree-day normalisation

A heating degree-day (HDD) is a day where the mean outdoor temperature was below 15.5°C (the standard UK base temperature). Space heating gas consumption should scale roughly linearly with HDD when the boiler and building fabric are consistent.

```python
BASE_TEMP = 15.5   # °C — standard UK HDD base temperature

def heating_degree_days(daily_mean_temp: dict[date, float]) -> dict[date, float]:
    return {d: max(BASE_TEMP - temp, 0.0) for d, temp in daily_mean_temp.items()}

def normalised_heating_efficiency(daily_heating_kwh: dict[date, float],
                                   hdd: dict[date, float]) -> float:
    """
    Gas kWh per HDD — lower is more efficient.
    Typical range: 15–50 kWh/HDD depending on property size and insulation.
    """
    paired = [(daily_heating_kwh[d], hdd[d]) for d in daily_heating_kwh
              if d in hdd and hdd[d] > 0.5]   # exclude mild days with near-zero HDD
    if not paired:
        return None
    total_kwh = sum(p[0] for p in paired)
    total_hdd = sum(p[1] for p in paired)
    return total_kwh / total_hdd
```

### Step 3: COP model for air-source heat pumps

The coefficient of performance (COP) of an air-source heat pump (ASHP) varies with outdoor temperature. Use the Carnot-bounded model with a practical efficiency factor:

```python
TARGET_FLOW_TEMP = 45.0   # °C — typical for underfloor heating or modern radiators
                           # Use 55°C for older radiator systems (lower COP result)

ETA_ASHP = 0.45   # practical efficiency factor (fraction of Carnot COP)
                   # Range: 0.40–0.50 for modern UK-market ASHPs (MCS data)

def cop_at_outdoor_temp(t_outdoor: float,
                         t_flow: float = TARGET_FLOW_TEMP,
                         eta: float = ETA_ASHP) -> float:
    """
    Returns COP. Returns 1.0 if outdoor temp is so low that the heat pump
    is likely to use auxiliary electric resistance heating.
    """
    if t_outdoor <= -10.0:
        return 1.0   # below rated minimum — resistance backup dominates
    t_out_k  = t_outdoor + 273.15
    t_flow_k = t_flow + 273.15
    if t_flow_k <= t_out_k:
        return 6.0   # outdoor warmer than flow target — free cooling scenario
    cop_carnot = t_flow_k / (t_flow_k - t_out_k)
    return eta * cop_carnot
```

The choice of flow temperature is critical. Older radiator systems require 70°C flow, which yields COP ≈ 1.8 at 0°C — barely better than electric resistance. Modern underfloor or oversized radiators allow 45°C flow, yielding COP ≈ 2.6 at 0°C. Report both scenarios.

### Step 4: Annual cost comparison — gas vs heat pump

For each half-hourly period in the heating season:

```python
BOILER_EFFICIENCY = 0.89   # modern condensing gas boiler (ErP A-rated)
                            # Older non-condensing: use 0.72

def model_heat_pump_cost(heating_periods: list[tuple[date, int, float, float]],
                          elec_tariff: Tariff,
                          gas_rate_p_per_kwh: float,
                          flow_temp: float = TARGET_FLOW_TEMP) -> dict:
    """
    heating_periods: [(date, period_index, heating_gas_kwh, outdoor_temp_c)]
    heating_gas_kwh: space-heating gas for this period (base load already subtracted)
    """
    gas_cost_p        = 0.0
    hp_elec_cost_p    = 0.0
    hp_elec_kwh_total = 0.0
    gas_kwh_total     = 0.0

    for d, period, gas_kwh, t_outdoor in heating_periods:
        if gas_kwh <= 0:
            continue

        # thermal energy delivered by boiler
        thermal_kwh = gas_kwh * BOILER_EFFICIENCY

        # electricity the heat pump would need to deliver the same thermal energy
        cop = cop_at_outdoor_temp(t_outdoor, flow_temp)
        hp_elec_kwh = thermal_kwh / cop

        elec_rate_p = rate_for_period(elec_tariff, d, period)
        gas_cost_p     += gas_kwh    * gas_rate_p_per_kwh
        hp_elec_cost_p += hp_elec_kwh * elec_rate_p

        gas_kwh_total     += gas_kwh
        hp_elec_kwh_total += hp_elec_kwh

    return {
        'heating_gas_kwh_annual':      round(gas_kwh_total, 0),
        'heating_gas_cost_gbp_annual': round(gas_cost_p / 100, 2),
        'hp_elec_kwh_annual':          round(hp_elec_kwh_total, 0),
        'hp_elec_cost_gbp_annual':     round(hp_elec_cost_p / 100, 2),
        'annual_saving_gbp':           round((gas_cost_p - hp_elec_cost_p) / 100, 2),
        'mean_seasonal_cop':           round(gas_kwh_total * BOILER_EFFICIENCY
                                             / hp_elec_kwh_total, 2) if hp_elec_kwh_total > 0 else None,
    }
```

Run this twice: once with `flow_temp=45` (optimistic, oversized radiators) and once with `flow_temp=55` (conservative, standard UK radiators). Report the range.

### Step 5: Payback calculation

```python
GRANT_GBP = 7500   # Boiler Upgrade Scheme (BUS), valid as of mid-2026

def heat_pump_payback(installed_cost_gbp: float,
                       annual_saving_gbp: float,
                       grant_gbp: float = GRANT_GBP,
                       discount_rate: float = 0.035) -> dict:
    net_cost = max(installed_cost_gbp - grant_gbp, 0.0)

    if annual_saving_gbp <= 0:
        return {
            'payback_years': None,
            'npv_15yr_gbp':  None,
            'viable':        False,
            'reason':        'heat_pump_costs_more_than_gas',
        }

    simple_payback = net_cost / annual_saving_gbp
    npv_15 = sum(annual_saving_gbp / (1 + discount_rate) ** t
                 for t in range(1, 16)) - net_cost

    return {
        'installed_cost_gbp': installed_cost_gbp,
        'grant_gbp':          grant_gbp,
        'net_cost_gbp':       round(net_cost, 0),
        'annual_saving_gbp':  round(annual_saving_gbp, 2),
        'payback_years':      round(simple_payback, 1),
        'npv_15yr_gbp':       round(npv_15, 0),
        'viable':             simple_payback <= 15 and npv_15 > 0,
    }
```

Installed cost guidance (mid-2026 UK):
- 2–3 bed property, no major system changes required: £8,000–£12,000
- 4 bed, potential radiator upgrades needed: £12,000–£18,000

Surface installed cost as a range rather than a point estimate. The model cannot determine whether radiator upgrades are needed — flag this as a key uncertainty for the installer quote.

### Step 6: Suitability flags

Produce a checklist of conditions that affect viability. These are shown to the consumer alongside the financial model.

```python
def suitability_flags(result: dict, shape: dict) -> list[dict]:
    flags = []

    # Sufficient heating demand to justify installation
    flags.append({
        'check':    'annual_heating_demand',
        'pass':     result['heating_gas_kwh_annual'] >= 5000,
        'value':    result['heating_gas_kwh_annual'],
        'note':     'Below 5,000 kWh/year heating demand, payback period extends significantly.',
    })

    # Strong seasonal pattern (confirms gas is used for heating, not just hot water)
    flags.append({
        'check':    'seasonal_signal',
        'pass':     shape.get('winter_summer_gas_ratio', 1.0) >= 2.0,
        'value':    shape.get('winter_summer_gas_ratio'),
        'note':     'Low seasonal variation may indicate gas is primarily for hot water, not space heating.',
    })

    # Mean COP above break-even with gas
    # Break-even COP = gas_rate / elec_rate
    flags.append({
        'check':    'cop_above_breakeven',
        'pass':     result['mean_seasonal_cop'] is not None and
                    result['mean_seasonal_cop'] >= shape.get('breakeven_cop', 2.5),
        'value':    result['mean_seasonal_cop'],
        'note':     'If seasonal COP is below the electricity/gas price ratio, the heat pump is more expensive to run.',
    })

    # Financial viability
    flags.append({
        'check':    'financial_viability',
        'pass':     result.get('viable', False),
        'value':    result.get('payback_years'),
        'note':     'Payback should be under 15 years for a reasonable investment case.',
    })

    return flags
```

### Break-even COP

The heat pump is cost-neutral when:

```
COP_breakeven = electricity_rate_p / gas_rate_p
```

At current UK rates (electricity ~24p/kWh, gas ~6p/kWh), the break-even COP is 4.0. A modern ASHP delivers a seasonal average COP of 2.5–3.5 in a typical UK climate, which means the running cost saving depends critically on tariff choice. Consumers on a heat-pump-specific electricity tariff (lower overnight rate for direct heating control) see a more favourable break-even.

Include the break-even COP prominently in the output — it is the single most useful number for understanding the economics of the switch.

---

## 6. Shared Output Schema

### Service #1 — Tariff match result

```json
{
  "household_id": "...",
  "as_of_date": "2026-07-19",
  "current_tariff": "Existing Supplier Flat",
  "current_annual_cost_gbp": 1240.00,
  "consumption_shape": {
    "night_fraction": 0.28,
    "evening_peak_fraction": 0.19,
    "annual_kwh_estimate": 3850
  },
  "ranked_tariffs": [
    {
      "tariff": "Octopus Agile",
      "annual_cost_gbp": 980.00,
      "saving_gbp": 260.00,
      "saving_pct": 21.0,
      "ranking_stable": true,
      "eligibility": ["smart_meter_required"]
    }
  ]
}
```

### Service #2 — Battery optimisation result

```json
{
  "household_id": "...",
  "tariff_used": "Octopus Go",
  "payback_curve": [
    {"capacity_kwh": 5.0, "installed_cost_gbp": 3500, "annual_saving_gbp": 380,
     "payback_years": 9.2, "npv_10yr_gbp": 680},
    {"capacity_kwh": 10.0, "installed_cost_gbp": 7000, "annual_saving_gbp": 540,
     "payback_years": 13.0, "npv_10yr_gbp": 450}
  ],
  "recommended_capacity_kwh": 5.0,
  "recommendation_basis": "shortest_payback"
}
```

### Service #3 — Appliance disaggregation result

```json
{
  "household_id": "...",
  "weeks_analysed": 12,
  "appliances_detected": [
    {"appliance": "ev_fast", "likely_present": true, "match_count": 38,
     "mean_confidence": 0.74, "tou_shift_saving_gbp": 145.00}
  ],
  "total_shift_saving_gbp": 145.00
}
```

### Service #4 — Heat pump suitability result

```json
{
  "household_id": "...",
  "heating_gas_kwh_annual": 11200,
  "heating_gas_cost_gbp_annual": 672,
  "scenarios": {
    "optimistic_45c_flow": {
      "hp_elec_kwh_annual": 4310,
      "hp_elec_cost_gbp_annual": 518,
      "annual_saving_gbp": 154,
      "mean_seasonal_cop": 2.61,
      "payback_years": 29.2,
      "viable": false
    },
    "conservative_55c_flow": {
      "hp_elec_kwh_annual": 5620,
      "hp_elec_cost_gbp_annual": 675,
      "annual_saving_gbp": -3,
      "mean_seasonal_cop": 1.99,
      "payback_years": null,
      "viable": false
    }
  },
  "breakeven_cop": 4.0,
  "suitability_flags": [
    {"check": "annual_heating_demand", "pass": true,  "value": 11200},
    {"check": "seasonal_signal",       "pass": true,  "value": 3.4},
    {"check": "cop_above_breakeven",   "pass": false, "value": 2.61},
    {"check": "financial_viability",   "pass": false, "value": 29.2}
  ],
  "recommendation": "Marginal. At current tariff rates the running cost saving does not justify installation. Reassess if electricity/gas price ratio improves or if a heat-pump-optimised tariff is available."
}
```

---

## 7. Implementation Notes

### Ordering dependencies

Services #1 and #2 are independent and can run in parallel. Service #3 depends on the background profile built for #1. Service #4 requires the gas data cleaned in the same pipeline as #1 and uses the electricity tariff already modelled in #1. Build the consumption shape and weekly profile once; pass it to all four.

### Minimum history requirements

| Service | Minimum | Ideal |
|---|---|---|
| #1 Tariff matching | 4 weeks | 52 weeks (full seasonal cycle) |
| #2 Battery sizing | 8 weeks | 52 weeks |
| #3 Disaggregation | 8 weeks | 26 weeks |
| #4 Heat pump | 12 months | 24 months |

Service #4 requires a full heating season. A household onboarded in April will need to wait until the following April for a reliable heat pump recommendation.

### Tariff data freshness

Tariff rates change. The ranking from service #1 is valid only at the rates current when it was computed. Rerun the ranking whenever a tariff update is detected, or at least monthly. Cache the household consumption profile; only the rate schedule changes.

### Price sensitivity display

For services #2 and #4, show how the conclusion changes if energy prices shift ±20%. Battery payback is sensitive to the tariff spread (cheap/expensive rate gap), not the absolute level. Heat pump viability is sensitive to the electricity/gas price ratio. Both should be presented as ranges, not point estimates, because retail energy prices are volatile.

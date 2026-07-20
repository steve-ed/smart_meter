# Tier 4 Results — 2026-07-19

Regression window: 2023-10-01 to 2025-03-31
Comfort/cost window: 2024-10-01 to 2025-03-31

---

## Service #13 — EPC Measurement from Temperature Decay

| M | Dwelling | True HTC W/K | Fitted HLC W/K | Gap% | True τ h | Fitted τ h | Error | EPC Band |
|---|----------|-------------|----------------|------|----------|------------|-------|----------|
| 1 | 1970s semi, unimproved | 225.4 | 247.0 | +9.6% | 60.3 | 60.2 | −0.2% | F |
| 2 | 1990s semi, partial upgrade | 176.8 | 161.0 | −8.9% | 81.4 | 81.1 | −0.5% | E |
| 3 | 2005 detached, Part L 2002 | 163.5 | 163.7 | +0.1% | 123.2 | 123.1 | −0.1% | C |
| 4 | Pre-1919 terraced, solid brick | 338.0 | 324.7 | −3.9% | 48.8 | 48.5 | −0.6% | G |
| 5 | 2015 semi, Part L 2013 | 95.3 | 95.7 | +0.4% | 133.9 | 133.3 | −0.5% | C |

All five meters recover the correct EPC band. τ fitting accuracy is within 0.6% of ground truth — well inside the ±10% validation target.

Performance gaps (fitted HLC vs true HTC) are all classified as *consistent with reference* (within ±10%). M3 and M5 are within ±0.5%; M1/M2/M4 show 4–10% gaps driven by the capacitance lookup table assumption rather than fitting error.

---

## Service #13b — Rolling Monthly EPC Band

| M | Months | Band distribution |
|---|--------|-------------------|
| 1 | 15 | F × 15 |
| 2 | 16 | E × 16 |
| 3 | 18 | C × 17, D × 1 |
| 4 | 18 | G × 18 |
| 5 | 18 | C × 18 |

No spurious month-to-month band flipping. The 8-week rolling aggregate is stable across all meters.

---

## Service #14 — Comfort vs Cost

| M | Dwelling | Winter Cost | Comfort (18–22°C) | Cold periods | Health risk (<16°C) | Vacant spend |
|---|----------|-------------|-------------------|--------------|---------------------|--------------|
| 1 | 1970s semi | £855.64 | 15.1% | 4,452 | 2,760 | 21.8% |
| 2 | 1990s semi | £1,259.21 | 35.6% | 3,630 | 1,651 | 28.1% |
| 3 | 2005 detached | £1,132.31 | 60.1% | 2,248 | 772 | 24.8% |
| 4 | Pre-1919 terraced | £1,204.33 | 10.7% | 5,034 | 3,985 | 27.9% |
| 5 | 2015 semi | £1,164.95 | 87.8% | 685 | 66 | 28.2% |

### Key observations

- **M5 (2015 Part L 2013)** is the standout performer — 88% of occupied time in the comfort zone, only 66 health-risk periods, at broadly the same cost as older properties. Low HTC (95 W/K) means heat is retained between boiler cycles.
- **M4 (pre-1919 solid brick)** is the worst — EPC G, only 11% comfort, 3,985 periods below 16°C while occupied (a WHO health risk threshold). HTC of 338 W/K means the dwelling loses heat almost as fast as the boiler can supply it.
- **M1 (1970s unimproved)** has the lowest absolute cost (£856) not because it is efficient, but because the home cools so rapidly that boiler cycles are short and intermittent. Comfort is correspondingly poor at 15%.
- **Vacant spend** is consistently 22–28% across all meters, indicating heating schedules are poorly matched to occupancy in the synthetic model. In a real deployment this would trigger a schedule optimisation recommendation.

---

## Overnight-only event filter (23:00–05:30)

Running the τ fitting restricted to overnight periods removes the main real-world disturbances (solar gain, occupancy metabolic heat, cooking, daytime wind gusts). Results vs all-hours:

| M | Dwelling | τ all-hours | τ overnight | err all | err ovn | Events all | Events ovn | Band |
|---|----------|-------------|-------------|---------|---------|-----------|-----------|------|
| 1 | 1970s semi | 60.2h | 60.0h | −0.2% | −0.6% | 353 | 299 | F = F |
| 2 | 1990s semi | 81.1h | 81.0h | −0.5% | −0.6% | 388 | 327 | E = E |
| 3 | 2005 detached | 123.1h | 122.6h | −0.1% | −0.5% | 464 | 341 | C = C |
| 4 | Pre-1919 terraced | 48.5h | 48.5h | −0.6% | −0.7% | 340 | 316 | G = G |
| 5 | 2015 semi | 133.3h | 133.3h | −0.5% | −0.5% | 338 | 374 | C = C |

On synthetic data the two modes are near-identical (no occupancy noise in the model). On real sensor data the overnight filter is expected to produce a tighter, less biased τ distribution. M5 gains events under the overnight filter because its high insulation (τ = 134h) means the boiler rarely runs overnight, allowing long uninterrupted decay sequences. Event count reduction for other meters is ~10–15%, acceptable given the noise reduction benefit.

**Recommendation:** use overnight-only as the production default.

---

## Real-world noise and measurement duration

### Sources of disturbance on real temperature readings

In order of impact:

- **Occupancy behaviour** — metabolic heat (~80–120 W/person) raises room temperature 0.5–1°C/h; cooking spikes 1–5°C in kitchen zones; opening external doors causes a rapid step-down mimicking a faster τ
- **Solar gain** — south-facing rooms gain 3–8°C on a clear winter afternoon even at low sun angles; residual thermal lag persists into early evening
- **Heating system dynamics** — radiator overshoot 1–2°C above setpoint; residual heat in radiators continues warming for 15–30 min after boiler shuts off, inflating the apparent start temperature of a decay event
- **Wind speed** — amplifies ventilation losses night-to-night; a cold windy night shows a faster apparent τ than a calm night at the same outdoor temperature
- **Sensor placement and accuracy** — hallway thermostats run systematically cooler than living rooms; sensor self-heating adds a constant +0.2–0.5°C offset; NTC thermistors have ±0.5°C absolute accuracy

The overnight filter and the existing R² ≥ 0.85 / outdoor stability ±2°C guards already reject the worst events. Systematic biases (solar, occupancy) are harder — they pull τ estimates in a consistent direction and do not average out.

### Minimum nights for a reliable EPC band

Bootstrap simulation using 12% event-to-event τ scatter (representative of occupancy + solar residual + wind-driven ACH variation + sensor noise combined) and a 60% overnight capture rate:

| Events | ~Nights | ~Weeks | 95% CI half-width | Verdict |
|--------|---------|--------|-------------------|---------|
| 5 | 8 | 1 | ±8.7% | Borderline — only safe if well away from a band boundary |
| 10 | 16 | 2.3 | ±6.8% | Adequate rough screen |
| 20 | 33 | 5 | ±5.0% | **Minimum recommended** |
| 30 | 50 | 7 | ±4.2% | Good for most properties |
| 50 | 83 | 12 | ±3.3% | High confidence |
| 100 | 166 | 24 | ±2.3% | Needed near band boundaries |

EPC band margins in τ-space are typically 25–50%, so a ±5% CI is sufficient for mid-band properties. The ±4% achieved at 30 events (~7 weeks) is the recommended default operating point.

**Caveats:**

- The 12% scatter is a central estimate. A well-placed sensor in a stable room could achieve 8%; a hallway sensor adjacent to an open-plan kitchen could be 20%+. Variance scales as σ², so doubling scatter quadruples the events needed.
- Flagging poor-quality nights in near real-time (large outdoor temperature swings, occupancy anomalies detectable from electricity data) could lift effective capture rate to ~80%, reducing calendar time by roughly 25%.
- Properties near a band boundary require the full 100-event / 24-week dataset. The algorithm should flag when the fitted τ is within one CI half-width of a boundary and report the result as provisional pending more data.

---

## Service #13c — Heating-phase OLS regression

### Method

During a heating event the boiler output and indoor temperature are both known, giving both sides of the heat balance simultaneously:

```
Q_boiler (W) = HLC × (T_in - T_out) + C × dT/dt
```

This is fitted as a two-predictor OLS regression across all post-transient heating periods in the 18-month window. It recovers HLC and C independently in a single pass — no capacitance lookup table required.

**Critical filter — thermostat-clamped periods:** periods where `T_in >= setpoint − 0.5°C` are excluded. At these periods the boiler is maintaining temperature rather than raising it, so `dT/dt ≈ 0` while Q is large; including them attributes maintenance power entirely to the HLC×ΔT term, inflating HLC by 20–189% depending on how much time the thermostat spends active.

### Results

| M | Dwelling | HLC true | HLC heat | err | C true | C heat | err | τ err | R² | Band |
|---|----------|----------|----------|-----|--------|--------|-----|-------|----|------|
| 1 | 1970s semi | 225.4 | 225.4 | +0.0% | 13,600 | 13,487 | −0.8% | −0.9% | 1.000 | F |
| 2 | 1990s semi | 176.8 | 176.8 | −0.0% | 14,400 | 14,310 | −0.6% | −0.7% | 1.000 | E |
| 3 | 2005 detached | 163.5 | 163.5 | −0.0% | 20,150 | 20,068 | −0.4% | −0.4% | 1.000 | C |
| 4 | Pre-1919 terraced | 338.0 | 338.0 | +0.0% | 16,500 | 16,331 | −1.0% | −1.1% | 1.000 | G |
| 5 | 2015 semi | 95.3 | 95.3 | +0.0% | 12,760 | 12,712 | −0.4% | −0.4% | 1.000 | C |

All five meters recover HLC within 0.1% and C within 1.1% of ground truth. This is substantially better than the cooling-curve method (which had 4–10% HLC gaps driven by the capacitance lookup table assumption) because C is measured directly rather than assumed.

### Comparison with cooling-curve results

| M | Dwelling | Cooling HLC err | Heating HLC err | Cooling C source | Heating C err |
|---|----------|-----------------|-----------------|------------------|---------------|
| 1 | 1970s semi | +9.6% | **+0.0%** | lookup (175 Wh/K/m²) | −0.8% |
| 2 | 1990s semi | −8.9% | **−0.0%** | lookup (145 Wh/K/m²) | −0.6% |
| 3 | 2005 detached | +0.1% | **−0.0%** | lookup (155 Wh/K/m²) | −0.4% |
| 4 | Pre-1919 terraced | −3.9% | **+0.0%** | lookup (210 Wh/K/m²) | −1.0% |
| 5 | 2015 semi | +0.4% | **+0.0%** | lookup (145 Wh/K/m²) | −0.4% |

The heating regression eliminates the lookup table bias. On real data the advantage will be smaller (boiler efficiency uncertainty ~±5% maps directly into HLC error) but the method still removes the largest source of systematic error in the cooling approach.

### Combined approach

Running both methods on the same property gives a cross-validation check: if HLC from heating and HLC from cooling agree within ~5%, the system is self-consistent. If they diverge it flags a problem — likely the boiler efficiency assumption (heating) or the capacitance lookup (cooling). The best estimate of both HLC and C is then the heating regression result, with the cooling τ as a redundant check on τ = C/HLC.

### Real-world caveats

- **Boiler efficiency uncertainty** (~±5%) maps directly to ±5% on HLC — the dominant error source for the heating method, equivalent to the capacitance lookup error for the cooling method
- **DHW contamination** — summer base-load subtraction handles this but errors in the base-load estimate introduce a constant offset into Q_boiler
- **Boiler cycling** — on a 30-min meter a short on/off cycle produces a mixed reading; the `gas_heat < 0.05 kWh` filter rejects the noisiest periods but some cycling bias remains
- **Thermal lag** — the first period of each run is dropped (startup transient) but longer ramp-up in high-mass properties (m4 solid brick) may require skipping more periods

---

## Run details

```
python py/tier4_analysis.py   # run from project root
```

Output files:
- `data/tier4_summary_all.csv` — cooling curve, all hours
- `data/tier4_summary_overnight.csv` — cooling curve, overnight only
- `data/tier4_summary_heating.csv` — heating phase regression
- `data/m{1–5}_tier4_events.csv`
- `data/m{1–5}_tier4_rolling_epc.csv`

---

## Real-world disturbances affecting the comfort score

The comfort score measures the fraction of occupied time (07:00–22:30) where indoor temperature is in the 18–22°C zone. Disturbances fall into two categories: things that make the **measured temperature misleading**, and things that cause **genuine temperature excursions** the occupant actually feels.

### Sensor reads a temperature the occupant doesn't experience

**Spatial mismatch**
- Thermostat in hallway reads 2–4°C colder than the living room being occupied — score understates comfort
- A sensor near a radiator or in a south-facing room overstates it
- Single-point measurement misses room-to-room variation: a bedroom at 14°C while the living room is 20°C scores as comfortable, but the occupant sleeping in the bedroom is at health-risk temperature

**Thermal stratification**
- In poorly insulated rooms with high ceilings, floor-level temperature can be 3–5°C below head height — comfort at sensor height may not reflect occupant experience at floor or bed level

**Sensor self-heating and drift**
- Constant +0.2–0.5°C offset inflates the score slightly; drift over months skews trend analysis

### Genuine temperature excursions

**Occupancy schedule mismatch**
- The 07:00–22:30 occupied window is fixed in the model; real occupancy varies daily
- A retired household occupied until 23:30 has health-risk periods recorded as unoccupied (score too optimistic)
- A commuter household empty until 18:00 includes cold morning periods as occupied (score too pessimistic)

**Boiler and heating system failures**
- A boiler fault causing a 12-hour outage on a cold night produces a cluster of health-risk periods that are real events but one-off rather than structural, disproportionately distorting a weekly score

**Heating schedule misalignment**
- Pre-programmed timers set for an old routine register returning-home-to-cold-house time as occupied health-risk even though the occupant has just arrived
- Heating left on while away inflates occupied comfort score using energy spent on an empty building

**Thermal overshoot and undershoot**
- Poorly tuned thermostatic controls oscillate above and below setpoint; a property with a mean of 20°C can spend significant time above 22°C and below 18°C in alternation — the score penalises both

**Extreme cold weather**
- During a cold snap the boiler may not keep pace with heat loss even running continuously; comfort score legitimately drops but comparing scores across winters without weather-normalising penalises colder years unfairly

**Ventilation behaviour**
- Windows left open for air quality during mild spells drops temperature below 18°C and scores as a cold period even though the occupant chose to open the window

**Overheating in shoulder seasons**
- Late spring and early autumn solar gain can push temperature above 22°C; the model correctly counts these as outside the comfort zone but may surprise occupants who feel comfortable at 23°C

### Implications for the algorithm

**Occupancy detection from electricity data** is the highest-impact fix: a sustained base-load signature (TV, lighting) during the occupied window confirms occupation; an anomalously low load suggests the household is actually out. This is already in scope as a Tier 3 feature and would directly improve comfort score reliability without an additional sensor.

**Multi-zone temperature** is the second biggest improvement — even a single additional bedroom sensor alongside the thermostat would catch the most common mismatch (warm living room / cold bedroom at night) that a single-point score misses entirely.

**Weather normalisation** is needed before comparing comfort scores across winters or between properties in different climates — expressing cold-period counts relative to heating degree days removes the year-to-year weather signal and isolates building and behavioural performance.

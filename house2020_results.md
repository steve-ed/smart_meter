# House 2020 — EPC Estimation Results

Synthetic ground truth simulation for meter 15 (2020 semi, Part L 2021).
Full-year 2024 at 30-minute resolution with SMETS2-grade sensor noise applied.

## Dwelling

| Parameter | Value |
|---|---|
| Archetype | 2020 semi, Part L 2021 |
| Floor area | 88 m² |
| Boiler | 18 kW max, 89% efficiency |
| Setpoint schedule | 16°C setback / 20°C comfort |
| Internal gains | 100% of appliance electricity |
| Zone 2 (bedroom) | 22 m², G = 30 W/K inter-zone conductance |
| **True HTC** | **71.0 W/K** |
| **True tau** | **173.5 h** |
| **True EPC band** | **B** |

Annual simulation totals: electricity 5,132 kWh, gas 2,639 kWh.

Gas consumption is 76% lower than the 1975 house (10,935 kWh) on the same
floor area, setpoint schedule and occupancy pattern. Tau is 2.7× longer
(173.5 h vs 65.1 h), reflecting the combination of lower HTC and lower
thermal mass per unit area (kappa = 140 vs 170 Wh/m²K).

## Sensor noise model

Identical to the 1975 house study.

| Channel | Model | Parameters |
|---|---|---|
| Outdoor temperature | Gaussian additive | σ = 0.3°C |
| Indoor temperature | Gaussian additive | σ = 0.2°C |
| Gas | Multiplicative proportional | σ = 1.0% |
| Electricity | Multiplicative proportional | σ = 0.5% |
| Occupancy (PIR) | Binary flip | FP = 2%, FN = 5% |
| Wind speed | Gaussian, clipped ≥ 0 | σ = 0.5 m/s |
| Boiler relay | Perfect | — |

---

## Method comparison — full year

### Method 1: free-cooling event detection

Events detected using monotone indoor temperature decay with boiler off.
Per-event RTS Kalman smoother applied before exponential tau fit.

| Config | Events | tau (h) | tau err | HLC (W/K) | HLC err | Band | Confidence |
|---|---|---|---|---|---|---|---|
| Zone 1 all-hours | 495 | 414.8 | +139.1% | 30.8 | −56.6% | A | LOW |
| Zone 1 overnight | 269 | 445.0 | +156.5% | 28.7 | −59.6% | A | LOW |
| Zone 2 overnight | 200 | 422.6 | +143.6% | 30.2 | −57.5% | A | LOW |

All three configs are 2–3 EPC bands off the true value. The root cause is the
same survivorship bias as for the 1975 house: sensor noise fragments long events
into short fragments. The problem is more severe here because tau = 173.5 h is
almost three times longer — even a genuine free-cooling event spanning a full
night covers only 7–8 h, a small fraction of tau, making the exponential slope
barely distinguishable from flat. The fitter is trying to read a 173 h curve
from an 8 h window.

### Method 2: forward simulation HTC fitting

Searches over an HTC scale factor (golden-section, ~20 simulation runs).
Loss = normalised RMSE(indoor temp) + normalised RMSE(gas, heating slots only).

| HTC (W/K) | HTC err | Band | RMSE_T | RMSE_G | Heating slots |
|---|---|---|---|---|---|
| 71.1 | **+0.1%** | **B** ✓ | 0.204°C | 0.050 kWh | 657 |

Recovers the true HTC to within 0.1 W/K despite having only 657 heating slots
(vs 2,164 for the 1975 house). The gas signal is weaker in absolute terms but
proportionally just as informative: each active heating slot constrains HTC
directly via the energy balance.

---

## Data window evaluation — htc_fit method

| Window | Slots | Heating slots | HTC (W/K) | Err% | Band | RMSE_T (°C) | RMSE_G (kWh) |
|---|---|---|---|---|---|---|---|
| Full year | 17,568 | 657 | 71.1 | +0.1% | B ✓ | 0.204 | 0.050 |
| 6 months (Jan–Jun) | 8,736 | 423 | 71.1 | +0.1% | B ✓ | 0.204 | 0.050 |
| 1 month (Jan) | 1,488 | 149 | 71.0 | −0.0% | B ✓ | 0.197 | 0.051 |
| 1 month (Jul) | 1,488 | 0 | 62.2 | −12.4% | B ✓ | 0.280 | — |
| 2 weeks (Jan) | 672 | 76 | 72.3 | +1.8% | B ✓ | 0.205 | 0.263 |
| 1 week (Jan) | 336 | 44 | 74.0 | +4.2% | B ✓ | 0.198 | 0.268 |
| 1 week (Jul) | 336 | 0 | 39.9 | −43.8% | **A ✗** | 0.404 | — |

### Observations

**Correct band on all windows except 1-week summer.** The 1975 house returned
the correct band even on 1-week July (+4.7%, band F). The 2020 house fails on
that same window (−43.8%, band A). The difference is tau: at 173.5 h the house
barely changes temperature over 7 days of summer, leaving almost no signal for
the fitter to work with.

**1-week winter still succeeds (+4.2%, band B).** Heating slots anchor the fit
even when the temperature signal is weak. With only 44 active heating slots the
gas RMSE spikes (0.268 vs 0.050 kWh) but the band estimate holds.

**Summer-only data becomes unreliable earlier.** 1-month July gives −12.4%
(still correct band, just). For a property with tau ≈ 173 h, a month of summer
observations sees only ~5% of the thermal time constant, compared to ~45% for
the 1975 house (tau 65 h). The effective signal-to-noise ratio for HTC from
temperature alone falls accordingly.

**Heating slots are proportionally more important for a well-insulated house.**
With 657 annual heating slots vs 2,164 for the 1975 house, every winter
observation carries more weight. Losing the heating season entirely (summer
only) creates a much larger accuracy degradation here than for the leakier house.

**The minimum reliable window is 1 month of heating season.** Full year, 6
months, and 1-month January all return correct band and sub-1% HTC error.
1-week January is correct but marginal. 1-week July fails.

---

## 2D fit: HTC and inter-zone conductance G

True values: HTC = 71.0 W/K, G = 30.0 W/K, band B.

Note: G/HTC ≈ 42% for this dwelling vs 13% for the 1975 house. The inter-zone
coupling represents a much larger fraction of total heat transfer here, which
makes it simultaneously more important to characterise and more likely to
confuse a single-zone model.

### Full-year validation

| Method | HTC (W/K) | HTC err | G (W/K) | G err | Band | RMSE_T1 | RMSE_T2 |
|---|---|---|---|---|---|---|---|
| 1D (HTC only) | 71.1 | +0.1% | — | — | B | 0.204°C | — |
| 2D (HTC + G) | 71.1 | +0.1% | 29.9 | −0.3% | B | 0.204°C | 0.231°C |

Both parameters recovered to within 0.3% on a full year — better G recovery
than the 1975 house (−1.3%). With G representing a larger share of total heat
transfer, zone 2 temperature is more sensitive to G, giving a stronger
constraint.

### Data window comparison

| Window | Slots | Heat. | 1D z1 err | 1D z2 app HTC | 1D z2 err | 2D HTC err | 2D G err | Band |
|---|---|---|---|---|---|---|---|---|
| Full year | 17,568 | 657 | +0.1% | 71.1 | +0.1% | +0.1% | −0.3% | B ✓ |
| 6 months (Jan–Jun) | 8,736 | 423 | +0.1% | 71.1 | +0.1% | +0.1% | −0.3% | B ✓ |
| 1 month (Jan) | 1,488 | 149 | −0.0% | 71.0 | −0.0% | −0.0% | +0.0% | B ✓ |
| 1 month (Jul) | 1,488 | 0 | −12.4% | 61.0 | −14.1% | −12.7% | +25.3% | B ✓ |
| 2 weeks (Jan) | 672 | 76 | +1.8% | 74.4 | +4.8% | +3.4% | −4.7% | B ✓ |
| 1 week (Jan) | 336 | 44 | +4.2% | 88.9 | +25.2% | +13.9% | −13.7% | B ✓ |
| 1 week (Jul) | 336 | 0 | −43.8% | 53.4 | −24.8% | −40.3% | −36.0% | **A ✗** |

### Observations

**G is recovered to within 0.3% on 1-month winter or longer.** Better
precision than the 1975 house because the high G/HTC ratio (42%) makes zone 2
temperature more sensitive to the inter-zone coupling.

**Zone 2 1D diagnostic shows the G signal clearly.** On 1-week January, zone 1
1D gives +4.2% (correct band B) while zone 2 1D gives +25.2% (wrong band C).
The 6-fold larger error is the G diagnostic — it directly reflects the inter-zone
coupling inflating the apparent HTC seen from zone 2.

**Summer data fails for all methods.** 1-week July gives wrong band A for all
three approaches (zone 1 1D: −43.8%, zone 2 1D: −24.8%, 2D: −40.3%). With
tau = 173.5 h and no heating signal, there is simply insufficient thermal
excitation over 7 summer days to constrain HTC. Unlike the 1975 house (tau 65 h),
the 2020 house temperature barely responds to 7 days of summer ambient variation.

**2D fit adds value on winter windows but not summer.** 1-week January: 2D
gives +13.9% vs 1D's +4.2% — the parameter correlation penalty applies again.
1-month January: all methods give essentially zero error. On summer data the 2D
fit offers no improvement over 1D because neither HTC nor G can be resolved
without heating-driven excitation.

### When to use each method

| Situation | Recommended method |
|---|---|
| ≥ 1 month of heating season data, zone 2 sensor present | 2D — recovers both HTC and G |
| 1-week winter, zone 2 available | 1D zone 1 — 2D parameter correlation too high |
| Any summer-only window | Neither reliable; await heating season data |
| No zone 2 sensor | 1D zone 1 only |

---

## Comparison with 1975 house

| Property | 1975 semi | 2020 semi |
|---|---|---|
| True HTC | 229.9 W/K | 71.0 W/K |
| True tau | 65.1 h | 173.5 h |
| True band | F | B |
| Annual gas | 10,935 kWh | 2,639 kWh |
| Heating slots | 2,164 | 657 |
| G/HTC ratio | 13% | 42% |
| 1D full-year err | +0.1% | +0.1% |
| Min window (correct band) | 1 week (any season) | 2 weeks (Jan only) |
| Summer 1-week reliable? | Yes (+4.7%, band F) | No (−43.8%, band A) |
| 2D G full-year err | −1.3% | −0.3% |

The forward simulation fitting method is equally accurate on a full year for
both dwellings (+0.1%). The 2020 house requires more data to achieve the same
reliability: summer-only data is insufficient, and the minimum winter window
for a correct band is the same (1 week) but with much less margin.

The zone 2 G diagnostic is more informative for the better-insulated house: the
larger G/HTC ratio produces a stronger discrepancy between zone 1 and zone 2 1D
estimates, making the coupling easier to detect from a shorter window.

---

## Implementation

| File | Role |
|---|---|
| `py/gen_ground_truth_m15.py` | Simulation driver, window evaluation |
| `py/simulation_runner.py` | `forward_simulate_two_zone` with `htc_scale`, `g_scale` |
| `py/tier4_analysis.py` | `fit_htc_from_observations`, `use_zone2`, `fit_g` |
| `py/sensor_model.py` | Noise application, RTS Kalman smoother |
| `data/ground_truth_m15_2024.csv` | 17,568-row output |

# House 1975 — EPC Estimation Results

Synthetic ground truth simulation for meter 6 (1975 semi-detached, pre-1976 regulations).
Full-year 2024 at 30-minute resolution with SMETS2-grade sensor noise applied.

## Dwelling

| Parameter | Value |
|---|---|
| Archetype | 1975 semi, pre-1976 regs |
| Floor area | 88 m² |
| Boiler | 24 kW max, 89% efficiency |
| Setpoint schedule | 16°C setback / 20°C comfort |
| Internal gains | 100% of appliance electricity |
| Zone 2 (bedroom) | 22 m², G = 30 W/K inter-zone conductance |
| **True HTC** | **229.9 W/K** |
| **True tau** | **65.1 h** |
| **True EPC band** | **F** |

Annual simulation totals: electricity 5,132 kWh, gas 10,935 kWh.

## Sensor noise model

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
| Zone 1 all-hours | 509 | 219.1 | +236.6% | 70.3 | −69.4% | B | LOW |
| Zone 1 overnight | 320 | 210.0 | +222.7% | 73.3 | −68.1% | B | LOW |
| Zone 2 overnight | 250 | 225.6 | +246.8% | 68.2 | −70.3% | B | LOW |

All three configs are 4–5 EPC bands off the true value. The root cause is
survivorship bias: Gaussian sensor noise fragments long events into short
fragments. Short events (4–8 points) under a tight Kalman smoother produce
near-flat smoothed decay, yielding massively over-estimated tau and
consequently under-estimated HLC.

### Method 2: forward simulation HTC fitting

Searches over an HTC scale factor (golden-section, ~20 simulation runs).
Loss = normalised RMSE(indoor temp) + normalised RMSE(gas, heating slots only).
Uses all 17,568 half-hour slots — heating-on periods contribute via gas
consumption; heating-off periods contribute via temperature decay rate.

| HTC (W/K) | HTC err | Band | RMSE_T | RMSE_G | Heating slots |
|---|---|---|---|---|---|
| 230.2 | **+0.1%** | **F** ✓ | 0.239°C | 0.098 kWh | 2,164 |

Recovers the true HTC to within 0.3 W/K from a full year of noisy observations.

---

## Data window evaluation — htc_fit method

Effect of reducing available data on HTC estimate accuracy.
Heating slots = half-hour periods with observed gas > 2× base load (0.08 kWh).

| Window | Slots | Heating slots | HTC (W/K) | Err% | Band | RMSE_T (°C) | RMSE_G (kWh) |
|---|---|---|---|---|---|---|---|
| Full year | 17,568 | 2,164 | 230.2 | +0.1% | F ✓ | 0.239 | 0.098 |
| 6 months (Jan–Jun) | 8,736 | 1,246 | 230.1 | +0.1% | F ✓ | 0.237 | 0.096 |
| 1 month (Jan) | 1,488 | 351 | 229.8 | −0.0% | F ✓ | 0.202 | 0.098 |
| 1 month (Jul) | 1,488 | 0 | 233.9 | +1.7% | F ✓ | 0.263 | — |
| 2 weeks (Jan) | 672 | 176 | 231.9 | +0.9% | F ✓ | 0.213 | 0.385 |
| 1 week (Jan) | 336 | 89 | 236.2 | +2.7% | F ✓ | 0.213 | 0.460 |
| 1 week (Jul) | 336 | 0 | 240.8 | +4.7% | F ✓ | 0.606 | — |

### Observations

**Correct EPC band in every case**, including one week of summer data with zero
heating contribution. The method is far more robust than event detection across
all window lengths.

**Winter outperforms summer at equal window length.** One-week January (+2.7%)
beats one-week July (+4.7%) because heating slots directly constrain HTC via
measured gas consumption. Temperature alone carries less information about tau
when the indoor–outdoor temperature differential is small.

**Summer still works.** Daily temperature variation driven by internal gains,
occupancy, and solar coupling provides enough signal about the thermal time
constant to recover HTC within ~5% even with no heating data.

**One month of winter data matches six months.** January alone (351 heating
slots) gives −0.0% error, identical to 6 months of mixed data. The heating
season is the most information-dense period; additional summer data adds
little once sufficient heating events are available.

**RMSE_G spikes for 1-week winter** (0.46 vs 0.10 kWh typical) due to
high variance across only 89 active slots, but the temperature residual
compensates and the band estimate remains correct.

---

## Implementation

| File | Role |
|---|---|
| `py/gen_ground_truth_m6.py` | Simulation driver, window evaluation |
| `py/simulation_runner.py` | `forward_simulate` / `forward_simulate_two_zone` with `htc_scale` parameter |
| `py/tier4_analysis.py` | `fit_htc_from_observations`, `_golden_section` |
| `py/sensor_model.py` | Noise application, RTS Kalman smoother |
| `data/ground_truth_m6_2024.csv` | 17,568-row output (ground truth + obs + smoothed) |

---

## How htc_fit works

The old method tries to read the building's thermal fingerprint from the *shape*
of temperature curves during specific events. The new method does the opposite:
it runs the full physics simulation and asks "what HTC makes the simulation
match what we actually measured?"

### The search

There is one free parameter: an HTC scale factor (how much to multiply the
nominal HTC). The optimizer runs the forward simulation repeatedly with
different scale values, each time computing how well the simulated indoor
temperature and gas consumption match the sensor observations. It uses
golden-section search — a bracket-halving algorithm that needs around 20
simulation runs to converge to 0.1% tolerance.

### The loss function

```
loss = RMSE(T_sim, T_obs) / σ(T_obs)
     + RMSE(G_sim, G_obs) / σ(G_obs)   [heating slots only]
```

Both terms are divided by the observed standard deviation so they contribute
equally regardless of units. The gas term only uses slots where the boiler was
active — those are the slots where gas consumption is sensitive to HTC.

### Why it works where event detection fails

Event detection throws away ~85% of the data (everything except boiler-off,
monotone-decay periods) and tries to infer HTC from the *rate* of temperature
drop in the remainder. Sensor noise fragments those events, biasing the rate
estimate badly.

The fitting method uses all 17,568 slots:

- **Heating-on slots**: the simulation must burn the right amount of gas to
  maintain the setpoint. If HTC is too high, the simulated boiler runs harder
  than observed; too low, it runs less. Gas consumption is a direct linear
  function of HTC when the setpoint is held.

- **Heating-off slots**: the simulation must decay at the right rate toward
  outdoor temperature. This is where tau = C/HTC is constrained — the same
  physics as event detection, but using every boiler-off slot rather than a
  curated subset.

These two signals are complementary. The gas term pins down HTC precisely in
winter. The temperature term fills in when gas data is absent (summer).
Together they make the estimate robust across all data windows.

### What it assumes

The dwelling's **thermal mass C is taken as known** (from the archetype —
160 Wh/m²K × 88 m² = 14,080 Wh/K). Only HTC is fitted. If the actual
thermal mass differs significantly from the archetype value, the tau estimate
would be correct but the HTC derived from it would be biased. This is the same
assumption event detection makes implicitly.

It also assumes the **setpoint schedule, occupancy model, and internal gains**
used in the simulation are representative of reality. Errors there show up as a
systematic offset in the temperature residual that the HTC scale factor
partially absorbs — which is why the method still works in summer despite
having no gas signal to anchor it.

---

## 2D fit: HTC and inter-zone conductance G

With a second temperature sensor (bedroom, zone 2), the fitting can be extended
to two free parameters: `htc_scale` and `g_scale`. The Nelder-Mead simplex
algorithm replaces the golden-section search.

Zone 2 is unheated, so its temperature is driven by:

```
dT2/dt = HTC2 × (T_out − T2) / C2  +  G × (T1 − T2) / C2
```

The zone 1 signal is mainly sensitive to total HTC and gas consumption; the
zone 2 signal is additionally sensitive to G. Adding zone 2 to the loss
provides an independent equation that allows the optimizer to separate fabric
heat loss from inter-zone coupling.

True values: HTC = 229.9 W/K, G = 30.0 W/K, band F.

### Full-year validation

| Method | HTC (W/K) | HTC err | G (W/K) | G err | Band | RMSE_T1 | RMSE_T2 |
|---|---|---|---|---|---|---|---|
| 1D (HTC only) | 230.2 | +0.1% | — | — | F | 0.239°C | — |
| 2D (HTC + G) | 230.4 | +0.2% | 29.6 | −1.3% | F | 0.239°C | 0.270°C |

Both parameters recovered accurately from a full year of noisy observations.

### Data window comparison

| Window | Slots | Heat. | 1D HTC err | 2D HTC err | 2D G err | Band |
|---|---|---|---|---|---|---|
| Full year | 17,568 | 2,164 | +0.1% | +0.2% | −1.3% | F ✓ |
| 6 months (Jan–Jun) | 8,736 | 1,246 | +0.1% | +0.1% | −1.3% | F ✓ |
| 1 month (Jan) | 1,488 | 351 | −0.0% | −0.1% | +0.3% | F ✓ |
| 1 month (Jul) | 1,488 | 0 | +1.7% | +2.6% | −21.3% | F ✓ |
| 2 weeks (Jan) | 672 | 176 | +0.9% | +2.3% | −10.7% | F ✓ |
| 1 week (Jan) | 336 | 89 | +2.7% | +13.3% | −24.0% | F ✓ |
| 1 week (Jul) | 336 | 0 | +4.7% | +5.2% | −9.3% | F ✓ |

### Observations

**G is well-constrained when heating data is available.** With a full year or
six months, G is recovered to within 1.3%. One month of winter gives 0.3%.
The bedroom temperature responds differently during heating-on vs heating-off
periods, and this contrast is what pins down the inter-zone conductance.

**Without heating data, G becomes underdetermined.** On summer-only windows,
the zone 1–zone 2 temperature gap is driven entirely by the time-varying
interaction between internal gains and G. With no large forced steps (boiler
on/off), the optimizer cannot cleanly separate HTC and G — G error reaches
−21% on a full summer month.

**HTC accuracy degrades in the 2D fit on short winter windows.** One week
winter: 1D gives +2.7% but 2D gives +13.3%. When G is underdetermined, the
Nelder-Mead trades HTC against G along a near-flat ridge in the loss surface.
The 1D fit avoids this by holding G fixed, making it more robust when data is
scarce.

**The correct EPC band is returned in all cases for both methods.** The HTC
errors, even at their worst (13.3% for 2D on 1-week winter), remain within
a single EPC band of the true value.

### When to use each method

| Situation | Recommended method |
|---|---|
| ≥ 1 month of heating season data, zone 2 sensor present | 2D — recovers both HTC and G |
| Short windows or summer-only data | 1D — more robust, G cannot be separated |
| No zone 2 sensor | 1D only |

---

## Zone 2 diagnostic: running 1D twice

Running the 1D fit a second time using zone 2 temperature instead of zone 1 as the
primary temperature signal reveals what the bedroom sensor "thinks" the HTC is. Because
zone 2 is unheated and coupled to zone 1 via G, its temperature dynamics mix fabric heat
loss (HTC2) with inter-zone coupling. A 1D fitter that cannot distinguish these two
effects compensates by adjusting htc_scale — producing a biased "apparent HTC".

The discrepancy between the zone 1 and zone 2 1D estimates is a diagnostic signal for G:
large discrepancy → strong coupling; zero discrepancy → zones are thermally independent.

True values: HTC = 229.9 W/K, G = 30.0 W/K, HTC2 = 57.5 W/K (zone 2 fabric only).

### Data window comparison

| Window | Slots | Heat. | 1D z1 err | 1D z2 app HTC | 1D z2 err | 2D HTC err | 2D G err | Band |
|---|---|---|---|---|---|---|---|---|
| Full year | 17,568 | 2,164 | +0.1% | 230.1 | +0.1% | +0.2% | −1.3% | F ✓ |
| 6 months (Jan–Jun) | 8,736 | 1,246 | +0.1% | 229.9 | +0.0% | +0.1% | −1.3% | F ✓ |
| 1 month (Jan) | 1,488 | 351 | −0.0% | 229.8 | −0.0% | −0.1% | +0.3% | F ✓ |
| 1 month (Jul) | 1,488 | 0 | +1.7% | 241.8 | +5.2% | +2.6% | −21.3% | F ✓ |
| 2 weeks (Jan) | 672 | 176 | +0.9% | 235.3 | +2.3% | +2.3% | −10.7% | F ✓ |
| 1 week (Jan) | 336 | 89 | +2.7% | 327.6 | +42.5% | +13.3% | −24.0% | **G ✗** |
| 1 week (Jul) | 336 | 0 | +4.7% | 243.6 | +6.0% | +5.2% | −9.3% | F ✓ |

### Observations

**Zone 2 1D matches zone 1 1D on long windows.** Over a full year or several
months, the gas term anchors the energy balance and the simulation's zone 2
temperature happens to be well-matched at the correct htc_scale. The coupling
G is implicitly captured because the simulation already includes it — the
optimizer just needs enough data to settle on the right scale.

**Zone 2 1D degrades sharply on short winter windows.** One week of January
data gives +42.5% error and the wrong EPC band (G instead of F). With only
89 heating slots, the zone 2 temperature signal is driven by brief boiler-on
events. G pulls zone 2 toward zone 1 during those events in a way that cannot
be distinguished from a higher HTC — the optimizer compensates by inflating
htc_scale dramatically.

**This is the clearest diagnostic signal for G.** Zone 1 1D gives +2.7% on
1-week winter data; zone 2 1D gives +42.5%. The 15-fold larger error directly
reflects the presence of G. In a real deployment this comparison would flag:
"zone 2 is strongly coupled to zone 1 — use the 2D fit once sufficient
heating-season data is available."

**Summer windows show moderate, consistent bias.** July 1-month: z1 gives
+1.7%, z2 gives +5.2%. July 1-week: z1 +4.7%, z2 +6.0%. The gap is present
but smaller than in winter because there are no boiler-on forcing events to
amplify the G effect — the coupling term G×(T1−T2) is smaller when the
zone 1–zone 2 differential is small.

**Default algorithm remains zone 1 1D.** Zone 2 1D is a diagnostic tool only.
It should not be used to estimate HTC for EPC purposes: it returns the wrong
band on 1-week winter data, which is precisely the scenario where fast
estimates might be needed.

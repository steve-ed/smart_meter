# All Houses — 1D htc_fit EPC Estimation Results

Forward simulation HTC fitting (1D, zone 1 temperature + gas) evaluated across
all 15 dwelling archetypes. Full-year 2024 simulation at 30-minute resolution
with SMETS2-grade sensor noise. Raw sensor observations used throughout (Kalman-
smoothed inputs were tested and found to introduce systematic negative bias —
see below).

---

## Dwelling fleet

| M | Label | HTC (W/K) | tau (h) | Band | HTC/m² | Band position | Margin to next band |
|---|---|---|---|---|---|---|---|
| 1 | 1970s semi, unimproved | 225.4 | 60.3 | F | 2.651 | 36% | +20.7% |
| 2 | 1990s semi, partial upgrade | 176.8 | 81.4 | E | 1.965 | 36% | +19.6% |
| 3 | 2005 detached, Part L 2002 | 163.5 | 123.2 | C | 1.258 | 88% | +3.4% |
| 4 | Pre-1919 solid brick terraced | 338.0 | 48.8 | G | 4.506 | 20% | +119.7% |
| 5 | 2015 semi, Part L 2013 | 95.3 | 133.9 | C | 1.083 | 38% | +20.1% |
| 6 | 1975 semi, pre-1976 regs | 229.9 | 65.1 | F | 2.612 | 31% | +22.5% |
| 7 | 1980 semi, 1976 regs | 224.8 | 64.6 | F | 2.554 | 24% | +25.3% |
| 8 | 1985 semi, 1985 regs | 203.8 | 69.1 | E | 2.315 | 94% | +1.5% |
| 9 | 1990 semi, Part L 1990 | 184.3 | 75.5 | E | 2.094 | 57% | +12.2% |
| 10 | 1995 semi, Part L 1995 | 160.3 | 85.1 | E | 1.822 | 12% | +29.0% |
| 11 | 2000 semi, Part L 2000 | 133.8 | 98.6 | D | 1.521 | 49% | +15.1% |
| 12 | 2005 semi, Part L 2002 | 124.4 | 106.1 | D | 1.414 | 25% | +23.8% |
| 13 | 2010 semi, Part L 2010 | 109.9 | 118.5 | C | 1.249 | 85% | +4.1% |
| 14 | 2015 semi, Part L 2013 | 95.3 | 133.9 | C | 1.083 | 38% | +20.1% |
| 15 | 2020 semi, Part L 2021 | 71.0 | 173.5 | B | 0.807 | 43% | +17.7% |

Fleet spans bands G–B, HTC 71–338 W/K, tau 49–174 h. Annual gas ranges from
2,640 kWh (m15) to 15,786 kWh (m4) on identical occupancy and setpoint schedules.

---

## Full-year results

**15/15 correct band. All HTC errors within ±0.2%.**

| M | Label | True HTC | Band | Fit HTC | Err% | Fit band | Heating slots |
|---|---|---|---|---|---|---|---|
| 1 | 1970s semi, unimproved | 225.4 | F | 225.6 | +0.1% | F ✓ | 2,141 |
| 2 | 1990s semi, partial upgrade | 176.8 | E | 177.1 | +0.2% | E ✓ | 1,822 |
| 3 | 2005 detached, Part L 2002 | 163.5 | C | 163.8 | +0.2% | C ✓ | 1,636 |
| 4 | Pre-1919 solid brick terraced | 338.0 | G | 338.2 | +0.1% | G ✓ | 2,642 |
| 5 | 2015 semi, Part L 2013 | 95.3 | C | 95.3 | +0.0% | C ✓ | 1,065 |
| 6 | 1975 semi, pre-1976 regs | 229.9 | F | 230.2 | +0.1% | F ✓ | 2,164 |
| 7 | 1980 semi, 1976 regs | 224.8 | F | 225.1 | +0.1% | F ✓ | 2,136 |
| 8 | 1985 semi, 1985 regs | 203.8 | E | 204.0 | +0.1% | E ✓ | 2,021 |
| 9 | 1990 semi, Part L 1990 | 184.3 | E | 184.6 | +0.2% | E ✓ | 1,868 |
| 10 | 1995 semi, Part L 1995 | 160.3 | E | 160.6 | +0.2% | E ✓ | 1,684 |
| 11 | 2000 semi, Part L 2000 | 133.8 | D | 134.0 | +0.1% | D ✓ | 1,442 |
| 12 | 2005 semi, Part L 2002 | 124.4 | D | 124.6 | +0.1% | D ✓ | 1,346 |
| 13 | 2010 semi, Part L 2010 | 109.9 | C | 110.0 | +0.1% | C ✓ | 1,215 |
| 14 | 2015 semi, Part L 2013 | 95.3 | C | 95.3 | +0.0% | C ✓ | 1,065 |
| 15 | 2020 semi, Part L 2021 | 71.0 | B | 71.1 | +0.1% | B ✓ | 653 |

The method is robust across the full range: G-rated pre-1919 solid brick terraced
(HTC 338 W/K, tau 49 h) through B-rated 2020 Part L 2021 semi (HTC 71 W/K,
tau 174 h). HTC error is consistently ≤0.2% regardless of dwelling type, age,
or construction.

---

## Band correctness by data window

Err% shown relative to true HTC. Band shown after error. ✓ = correct, ✗ = wrong band.

| M | Band | tau (h) | Full year | 6 months | 1 mo Jan | 1 mo Jul | 2 wk Jan | 1 wk Jan | 1 wk Jul |
|---|---|---|---|---|---|---|---|---|---|
| 1 | F | 60.3 | +0.1% F ✓ | +0.0% F ✓ | −0.1% F ✓ | +1.8% F ✓ | +0.9% F ✓ | +2.8% F ✓ | +4.5% F ✓ |
| 2 | E | 81.4 | +0.2% E ✓ | +0.1% E ✓ | −0.1% E ✓ | −1.6% E ✓ | +1.2% E ✓ | +3.4% E ✓ | +5.2% E ✓ |
| 3 | C | 123.2 | +0.2% C ✓ | +0.1% C ✓ | −0.2% C ✓ | −5.2% C ✓ | +1.8% C ✓ | +3.9% **D ✗** | +7.8% **D ✗** |
| 4 | G | 48.8 | +0.1% G ✓ | +0.0% G ✓ | −0.1% G ✓ | +5.9% G ✓ | +0.8% G ✓ | +1.6% G ✓ | +5.6% G ✓ |
| 5 | C | 133.9 | +0.0% C ✓ | +0.0% C ✓ | −0.2% C ✓ | −7.7% C ✓ | +1.5% C ✓ | +3.9% C ✓ | −7.2% C ✓ |
| 6 | F | 65.1 | +0.1% F ✓ | +0.1% F ✓ | −0.0% F ✓ | +1.7% F ✓ | +0.9% F ✓ | +2.7% F ✓ | +4.7% F ✓ |
| 7 | F | 64.6 | +0.1% F ✓ | +0.1% F ✓ | −0.1% F ✓ | +1.6% F ✓ | +0.9% F ✓ | +2.9% F ✓ | +4.6% F ✓ |
| 8 | E | 69.1 | +0.1% E ✓ | +0.1% E ✓ | −0.1% E ✓ | +0.6% E ✓ | +1.2% E ✓ | +3.4% **F ✗** | +4.7% **F ✗** |
| 9 | E | 75.5 | +0.2% E ✓ | +0.1% E ✓ | −0.0% E ✓ | −0.6% E ✓ | +1.3% E ✓ | +3.3% E ✓ | +4.8% E ✓ |
| 10 | E | 85.1 | +0.2% E ✓ | +0.1% E ✓ | −0.0% E ✓ | −1.9% E ✓ | +1.5% E ✓ | +3.6% E ✓ | +5.1% E ✓ |
| 11 | D | 98.6 | +0.1% D ✓ | +0.1% D ✓ | −0.0% D ✓ | −3.8% D ✓ | +1.5% D ✓ | +3.6% D ✓ | +5.2% D ✓ |
| 12 | D | 106.1 | +0.1% D ✓ | +0.1% D ✓ | −0.1% D ✓ | −4.7% D ✓ | +1.7% D ✓ | +3.9% D ✓ | +5.1% D ✓ |
| 13 | C | 118.5 | +0.1% C ✓ | +0.1% C ✓ | −0.1% C ✓ | −6.6% C ✓ | +1.6% C ✓ | +3.8% C ✓ | +4.4% **D ✗** |
| 14 | C | 133.9 | +0.0% C ✓ | +0.0% C ✓ | −0.2% C ✓ | −7.7% C ✓ | +1.5% C ✓ | +3.9% C ✓ | −7.2% C ✓ |
| 15 | B | 173.5 | +0.1% B ✓ | +0.1% B ✓ | −0.2% B ✓ | −12.4% B ✓ | +1.8% B ✓ | +4.2% B ✓ | −43.8% **A ✗** |

**Summary: 15/15 correct on full year, 6 months, 1 month Jan. 14/15 on 1 month Jul and 2 weeks Jan. 13/15 on 1 week Jan. 11/15 on 1 week Jul.**

---

## Observations

### Full year, 6 months, 1 month Jan — universal success

Every dwelling returns the correct band with HTC error ≤0.2% on a full year,
and ≤0.2% on 1-month January. The gas signal during the heating season dominates
the loss function and anchors the estimate regardless of tau or HTC magnitude.

### 1-month summer — robust across 14/15

The only significant summer degradation is m15 (2020 semi, tau=174 h) at −12.4%
on 1-month July — still correct band B. Longer-tau houses lose more accuracy on
summer data because the indoor-outdoor temperature differential is small and
changes slowly, providing little information about HTC. The gas term is absent
(no heating). Despite this, all 15 houses return the correct band on 1-month July.

### Short-window failures are explained entirely by band-boundary proximity

The four houses that ever return the wrong band are:

| M | True band | HTC/m² | Margin to next band | Fails at |
|---|---|---|---|---|
| 3 | C | 1.258 | +3.4% | 1-week Jan, 1-week Jul |
| 8 | E | 2.315 | +1.5% | 1-week Jan, 1-week Jul |
| 13 | C | 1.249 | +4.1% | 1-week Jul only |
| 15 | B | 0.807 | +17.7% | 1-week Jul (no heating signal) |

M8 has only **+1.5% margin** to the E/F boundary — the smallest of any house in
the fleet. A short-window positive bias of +3.4% is enough to push it over into
F. M3 and M13 both sit at 87–88% through band C (margin ≤4.1%). M15 fails on
1-week July not from proximity but from the fundamental absence of a heating
signal in a high-tau house over 7 summer days.

Every other house has ≥12% margin to its band boundary and tolerates the short-
window bias without a band error.

### Short-window bias pattern

On winter windows the fitter shows a consistent **positive** bias (+1–5%):
heating slots are sparse, the gas RMSE has high variance, and the optimizer
settles slightly high. On summer windows the bias is **negative** for high-tau
houses (−7 to −44%) where temperature variation over a short window is too small
to constrain HTC, and the fitter drifts toward under-estimating heat loss.

| Window | Typical err range | Band failures |
|---|---|---|
| Full year | 0% to +0.2% | 0/15 |
| 6 months | 0% to +0.2% | 0/15 |
| 1 month Jan | −0.2% to 0% | 0/15 |
| 1 month Jul | −12% to +6% | 0/15 |
| 2 weeks Jan | +0.8% to +1.8% | 0/15 |
| 1 week Jan | +1.6% to +4.2% | 2/15 (m3, m8) |
| 1 week Jul | −44% to +8% | 4/15 (m3, m8, m13, m15) |

### Practical minimum window by dwelling type

| Dwelling position in band | Min reliable window |
|---|---|
| > 10% from upper boundary | 1 week (any season) |
| 5–10% from upper boundary | 2 weeks winter |
| < 5% from upper boundary | 1 month winter (flag as boundary case) |
| High tau (> 130 h), summer only | Not reliable — await heating season |

---

## Effect of Kalman smoothing on input temperatures

Smoothed indoor/outdoor temperatures (produced by the RTS Kalman smoother in
`sensor_model.py`) were tested as inputs to the fitter in place of raw
observations.

**Smoothing makes results consistently worse.** The Kalman smoother's low process
sigma (0.05°C/slot, tuned for event detection where slow change is expected) lags
behind real heating cycles. It under-predicts temperature rise during boiler-on
periods and over-predicts decay during boiler-off, introducing a systematic
negative bias in the HTC estimate.

| Window | Raw err (1975 F) | Smooth err (1975 F) | Raw err (2020 B) | Smooth err (2020 B) |
|---|---|---|---|---|
| Full year | +0.1% | −0.2% | −0.2% | −0.4% |
| 1 month Jan | −0.0% | −0.6% | −1.7% | −3.0% |
| 1 month Jul | +1.7% | −4.7% | −12.4% | **−14.4% (A ✗)** |
| 1 week Jan | +2.7% | −0.1% | +3.5% | +1.0% |
| 1 week Jul | +4.7% | −2.4% | −43.8% | −52.3% |

Smoothing causes a band error on 2020 house 1-month July (B→A) that the raw
fitter avoids. The occasional smaller absolute error on winter short windows is
coincidental — the smoother is pulling in the wrong direction.

**Raw sensor observations are the correct input for htc_fit.** The smoother is
retained in the pipeline for event-detection methods where it was designed.

---

## Implementation

| File | Role |
|---|---|
| `py/gen_ground_truth_all.py` | Batch simulation for all 15 dwellings |
| `py/gen_ground_truth_m6.py` | Detailed analysis: 1975 semi (band F) |
| `py/gen_ground_truth_m15.py` | Detailed analysis: 2020 semi (band B) |
| `py/tier4_analysis.py` | `fit_htc_from_observations` — 1D and 2D fitting |
| `py/simulation_runner.py` | Forward simulation with `htc_scale` parameter |
| `data/ground_truth_m{1-15}_2024.csv` | 17,568-row ground truth + sensor data per dwelling |

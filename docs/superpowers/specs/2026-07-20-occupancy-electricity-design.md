# Electricity-Based Occupancy Detector — Design Spec
*2026-07-20*

---

## Overview

A new occupancy signal source for the Tier 3 signal fusion stack that infers OCCUPIED / VACANT / UNKNOWN labels from electricity half-hourly consumption alone. No additional sensors required. Feeds into Services #11 (vacancy-aware anomaly suppression), #12 (phantom load detection), and #14 (comfort vs cost) for households that have no PIR, CO₂, or phone-presence signals.

The detector is based on the always-on floor: the electricity consumed when nobody is home (fridges, routers, standby loads). Sustained load above the floor indicates presence; sustained load at the floor indicates absence.

---

## Position in the signal fusion stack

The detector inserts two entries into the existing priority hierarchy in `tier3_occupancy.md`:

```
1. Manual away calendar          → VACANT  (highest confidence)
2. CO₂ ≥ threshold               → OCCUPIED
3. Phone presence confirmed       → OCCUPIED
4. PIR trigger                   → OCCUPIED
4.5 Elec sustained above floor   → OCCUPIED   ← new
5. CO₂ < threshold (sustained)   → VACANT
6. Phone absent (sustained)      → VACANT
6.5 Elec sustained at floor      → VACANT    ← new
7. No signal                     → UNKNOWN
```

Position 4.5: a sustained above-floor electricity load is strong positive evidence of presence, comparable to PIR, but carries slightly more ambiguity because a single appliance left running can produce it.

Position 6.5: the VACANT assertion from electricity is weaker than CO₂ or phone absence. A household with all appliances off could still be home. The higher sustained-run requirement (6 periods vs 3 for CO₂) reflects this.

For households with no sensors at all, this is the only occupancy signal. OCCUPIED is reliable; VACANT is conservative.

---

## Always-on floor learning

### Bootstrap (no sensor data)

Overnight periods 01:00–05:30 (period indices 2–10) serve as a vacancy proxy. The floor is the P20 of all overnight readings across the trailing 8 weeks.

```python
OVERNIGHT_PERIODS = range(2, 11)   # 01:00–05:30 inclusive
FLOOR_PERCENTILE  = 20
MIN_NIGHTS        = 14             # cold-start threshold
```

P20 rather than median: occasional overnight active use (night shifts, insomnia) inflates the distribution; P20 is resistant to those events.

### Refinement (sensor-confirmed VACANT available)

When any higher-priority signal source produces confirmed VACANT labels, those periods replace overnight readings as the floor sample. Sensor-confirmed VACANT covers all 48 slots rather than just overnight, giving a more accurate floor. `floor_source` flips from `overnight_bootstrap` to `sensor_calibrated`.

### Stability tracking

The floor is recalculated weekly on a rolling 8-week window. If the new floor differs from the previous week's value by more than 25%, hold the previous value and set `floor_stable = False`. A sudden jump indicates contamination (electric heating, overnight guest, new appliance) rather than a genuine change. If instability persists for 3 or more consecutive weeks, accept the new level as a genuine step change and log a `floor_step_change` event — this is also useful input to Service #12 standby trend detection.

### Electric heating guard

Storage heaters and direct electric heating running overnight would corrupt the bootstrap floor. Guard condition: if the median overnight electricity across the trailing 2 weeks exceeds 0.5 kWh/period AND outdoor temperature is below 7°C, set `heating_contaminated = True`. When active:

- Overnight at-floor periods are not back-labelled VACANT; they remain UNKNOWN.
- Daytime OCCUPIED assertions are unaffected.
- The guard deactivates when either condition clears.

---

## Detection logic

### OCCUPIED assertion

Two tiers distinguish brief spikes (kettle, microwave) from sustained presence:

```python
OCCUPIED_EXCESS_KWH = 0.05    # 100W above floor — hard threshold, 1 period sufficient
OCCUPIED_SOFT_KWH   = 0.025   # 50W above floor — soft threshold, requires 2 consecutive periods

floor_mad = max(mad_of_floor_sample, 0.005)

occupied_threshold_hard = floor_kwh + max(OCCUPIED_EXCESS_KWH, 3.0 * floor_mad)
occupied_threshold_soft = floor_kwh + max(OCCUPIED_SOFT_KWH,  1.5 * floor_mad)
```

- Load ≥ hard threshold for 1 period → OCCUPIED immediately (`elec_above_floor_hard`)
- Load ≥ soft threshold for ≥ 2 consecutive periods → OCCUPIED (`elec_above_floor_soft`)

The MAD term adapts to households with variable always-on loads (e.g., noisy fridge-freezer compressor cycles). The minimum absolute excess prevents the threshold from collapsing to zero for very efficient households.

### VACANT assertion

```python
VACANT_RATIO       = 1.40   # load ≤ floor × 1.40 qualifies as "at floor"
VACANT_MIN_PERIODS = 6      # 3 consecutive hours required
```

A period qualifies as at-floor when `elec_kwh ≤ floor_kwh × VACANT_RATIO`. Once 6 consecutive at-floor periods accumulate, all 6 are back-labelled VACANT. Subsequent at-floor periods continue as VACANT until a non-at-floor period breaks the run.

Back-labelling is required: the 6-period run-up was also vacant; leaving those periods as UNKNOWN would undercount vacancy in the comfort score and phantom load baseline.

### UNKNOWN zone

Any period that is neither above an occupied threshold nor within an active at-floor run is UNKNOWN. This covers arrival and departure transitions and the mid-range where load is ambiguous.

### State transitions

Any OCCUPIED assertion (hard or soft) during an active VACANT run immediately terminates VACANT. The at-floor run counter resets; 6 new consecutive at-floor periods are required before VACANT can be re-asserted.

For the hard threshold: a single period above the threshold terminates VACANT and asserts OCCUPIED immediately.

For the soft threshold: two consecutive periods above the soft threshold are required before OCCUPIED is asserted. The first period alone is UNKNOWN, not OCCUPIED — so a single above-soft-threshold period does not break a VACANT run. Only the second consecutive period triggers the assertion and terminates VACANT, back-labelling the first period as OCCUPIED as well.

This prevents a fridge compressor spike in an otherwise empty house from generating a spurious OCCUPIED label, because compressor spikes fall within the MAD-adjusted soft threshold range rather than above the hard threshold, and a single-period soft exceedance does not trigger assertion.

---

## Cold-start

Below 14 nights of overnight data the floor is not reliable. During cold-start:

- All periods → UNKNOWN by default.
- OCCUPIED can still be asserted if load exceeds a conservative population-level floor:

```python
COLD_START_FLOOR_KWH = 0.030   # 60W — below any plausible occupied UK household baseline
```

This provides partial signal immediately without waiting for personalisation.

---

## Edge cases

| Condition | Behaviour |
|---|---|
| All-electric household (heat pump / storage heaters) | Heating contamination guard activates in winter; overnight VACANT suppressed; daytime OCCUPIED unaffected |
| Extended absence (holiday) | VACANT accumulates naturally; manual away calendar (priority 1) is preferred source for planned absences |
| Floor step change (new appliance) | Accepted after 3 consecutive weeks of instability; `floor_step_change` event logged |
| DST transition day (46 or 50 periods) | Exclude from floor sample accumulation and run-length counting; consistent with existing tier3 DST rule |
| Floor recalculation mid-week | Per-period output records carry floor fields at the time of calculation; no separate floor log required |

---

## Output schema

One record per period per day per household:

```python
{
  "household_id":         str,
  "date":                 "YYYY-MM-DD",
  "period_index":         int,      # 0–47
  "elec_kwh":             float,
  "floor_kwh":            float,
  "floor_mad_kwh":        float,
  "floor_source":         "overnight_bootstrap" | "sensor_calibrated",
  "floor_stable":         bool,
  "heating_contaminated": bool,
  "at_floor":             bool,     # elec_kwh ≤ floor_kwh × VACANT_RATIO
  "occupied_label":       "OCCUPIED" | "VACANT" | "UNKNOWN",
  "label_source":         "elec_above_floor_hard" | "elec_above_floor_soft"
                        | "elec_at_floor" | "cold_start" | None,
  "sustained_run":        int,      # consecutive periods in the current run
}
```

`label_source` distinguishes hard from soft OCCUPIED assertions. A hard assertion (single period, 100W+ above floor) carries more weight than a soft one when the fusion layer arbitrates conflicts between signals.

---

## Integration notes

- The floor learning and label generation live in a new module `py/occupancy_elec.py`.
- The existing `tier3_occupancy.md` signal fusion function is extended with two new source entries at positions 4.5 and 6.5.
- The `floor_step_change` event feeds into Service #12 (`detect_standby_trend`) as a corroborating signal.
- Weather data (outdoor temperature) is required for the electric heating guard; the existing `data/weather.csv` feed already provides this.
- No changes to the output schema of Services #11, #12, or #14 — the occupancy label and source fields they consume are unchanged. Only the set of possible `occupancy_source` values is extended.

---

## Validation approach (synthetic data)

The five synthetic meters have known occupancy schedules embedded in `home_model.py`. Validation metrics:

- **OCCUPIED precision / recall** against ground-truth occupied periods
- **VACANT precision / recall** against ground-truth vacant periods
- **UNKNOWN rate** — should decrease as floor stabilises after week 2
- **False OCCUPIED rate during confirmed vacancy** — target < 5% (driven by appliance spikes exceeding hard threshold)
- **Comfort score delta** — compare fixed 07:00–22:30 window comfort score against occupancy-corrected score; expect M4 (worst comfort) to show the largest correction

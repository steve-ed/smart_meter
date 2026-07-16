# Battery Size Analysis — Design Spec

**Date:** 2026-07-16
**MPAN:** 1234567891000 (only meter with both consumption and tariff data)

---

## Goal

Produce a Python script that prints a payback table for different home battery sizes, using real half-hourly consumption data and time-of-use tariff rates.

---

## Files

- `battery_simulator.py` — pure simulation module, no I/O
- `battery_analysis.py` — entry point: loads data, runs simulation, prints table

---

## Constants (top of `battery_analysis.py`)

```python
COST_PER_KWH_INSTALLED = 500   # £/kWh installed
BATTERY_SIZES_KWH = [2, 5, 7, 10, 13, 15]
ROUND_TRIP_EFFICIENCY = 0.90
MAX_C_RATE = 0.5                # max charge/discharge per hour as fraction of capacity
MIN_SOC = 0.20                  # don't discharge below 20% state of charge
WARRANTY_YEARS = 15             # payback beyond this is flagged
```

---

## Simulation Model (`battery_simulator.py`)

### Interface

```python
def simulate_day(consumption_hh, tariff_hh, battery_capacity_kwh) -> dict:
    ...
```

- `consumption_hh`: list of 48 floats (kWh per half-hour)
- `tariff_hh`: list of 48 floats (p/kWh for each half-hour)
- `battery_capacity_kwh`: float
- Returns: `{"daily_saving_p": float, "charge_cycled_kwh": float, "peak_kwh_displaced": float}`

### Per-day logic

Battery starts each day at MIN_SOC.

**Max energy per half-hour slot:**
```
max_half_hour_kwh = battery_capacity_kwh * MAX_C_RATE * 0.5
```

**Charging (off-peak slots):**
- Charge up to `max_half_hour_kwh`, capped by remaining capacity to 100% SOC.

**Discharging (peak slots):**
- Discharge to meet consumption demand, up to `max_half_hour_kwh`.
- Floor: don't go below MIN_SOC.
- Energy delivered = energy drawn from battery (efficiency already accounted for by only crediting what reaches the home).

**Daily saving:**
```
saving_p = units_discharged_kwh × (peak_rate_p - off_peak_rate_p)
```
Converted to £ for the output table.

---

## Data Loading (`battery_analysis.py`)

- Load `data/consumption.csv`, filter to `mpxn == 1234567891000` and `utility == electricity`.
- Load `data/tariff.csv`, filter to `mpan == 1234567891000` and `type == unit_rate`.
- Join on timestamp to produce per-day lists of 48 consumption and 48 tariff values.
- Skip incomplete days (fewer than 48 slots).

---

## Output

```
Battery Size Analysis — MPAN 1234567891000
Tariff: 8.78p off-peak / 16.29p peak  |  Installed cost: £500/kWh
Days simulated: X,XXX  |  Efficiency: 90%  |  Min SOC: 20%  |  Max C-rate: 0.5C

Size (kWh) | Installed Cost | Avg Daily Saving | Annual Saving | Payback (yrs)
-----------|----------------|------------------|---------------|---------------
         2 |         £1,000 |            12.3p |        £44.90 |          22.3 *
...

* Payback exceeds 15-year battery warranty period.
```

Rows where payback > 15 years are marked `*`.

---

## Testing

Unit tests in `tests/test_battery_simulator.py` covering:
- A day with no peak consumption — no saving
- A day with all peak consumption — battery fully cycles
- Battery too small to cover all peak demand — partial displacement
- Battery larger than daily consumption — saving capped by consumption, not battery size

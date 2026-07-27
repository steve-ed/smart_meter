# Solar Generation Dashboard Integration

**Date:** 2026-07-27
**Status:** Approved for implementation

## Goal

Surface measured solar generation data in the smart meter dashboard for households with solar meters (M2, M3, M14), and correct S01 tariff comparisons by adding Smart Export Guarantee (SEG) earnings as a net cost offset.

## Context

Three meters have half-hourly solar generation data in `production_clean.csv`:

| Meter | Generation MPXN | Total kWh | Date range |
|---|---|---|---|
| M2 | `2234567891000` | ~5,349 kWh | Jan 2023 – Jul 2026 |
| M3 | `5330642497188` | ~6,350 kWh | Jan 2022 – Jul 2026 |
| M14 | `1234567891038` | ~351 kWh | Apr 2026 – Jul 2026 |

The smart meter import readings already reflect net grid draw (solar self-consumption reduces import before it reaches the meter). SEG export earnings are currently unaccounted for in any service.

## Approach

Option B — per-period export calculation. For each half-hour period, `export = max(0, generation − consumption)`. This uses the actual half-hourly data, gives accurate SEG estimates, and lays groundwork for future battery optimisation in S02.

## Section 1: Config & Data Layer

### `config.py`

Add two constants:

```python
SOLAR_METERS = {
    2:  "2234567891000",
    3:  "5330642497188",
    14: "1234567891038",
}
SEG_RATE_P_KWH = 15.0   # Smart Export Guarantee pence/kWh
```

### `tier1_lib.py`

Add two functions:

**`load_solar_generation(meter_id, path="data/production_clean.csv") → list[dict]`**
- Returns `[]` immediately if `meter_id` not in `SOLAR_METERS`
- Otherwise reads `production_clean.csv`, filters by MPXN, deduplicates by timestamp
- Returns sorted list of `{timestamp, solar_kwh, period_index}` rows
- Applies `ELEC_CAP_KWH` cap to filter outliers (same guard as `load_electricity`)

**`compute_annual_export(consumption_rows, generation_rows) → dict`**
- Zips both series by timestamp
- Per half-hour: `export = max(0, generation - consumption)`
- Scales to 365 days using sample length (same scaling as `current_annual_cost`)
- Returns `{annual_export_kwh, annual_generation_kwh, days_in_sample}`
- Returns all-zeros dict if `generation_rows` is empty

## Section 2: Monthly Consumption Table

`_consumption_summary()` in `app.py` detects whether `meter_id` is in `SOLAR_METERS`.

For solar meters, each monthly row gains:

| Column | Description |
|---|---|
| `solar_kwh` | Total generation for that month |
| `export_kwh` | Estimated export = `max(0, generation − consumption)` per half-hour, summed monthly |
| `seg_earnings_gbp` | `export_kwh × SEG_RATE_P_KWH / 100`, rounded to 2dp |

For non-solar meters the table is unchanged — no empty columns added.

The cache key requires no changes since `SEG_RATE_P_KWH` is a compile-time constant.

## Section 3: S01 Tariff Comparison

`analyse_meter()` in `s01_tariff_matching.py` loads generation data and computes SEG earnings once per meter run:

```python
gen_rows = load_solar_generation(meter_id)
export = compute_annual_export(readings, gen_rows)
seg_earnings = round(export.get("annual_export_kwh", 0) * SEG_RATE_P_KWH / 100, 2)
```

Each output row gains:

| Column | Description |
|---|---|
| `seg_earnings_gbp` | Same value on every row — SEG rate is tariff-independent |
| `net_cost_gbp` | `annual_cost_gbp − seg_earnings_gbp` |

Saving comparisons (`saving_vs_current_gbp`, `saving_pct`) remain based on gross import costs — since SEG earnings are equal across all tariffs they do not affect ranking. `net_cost_gbp` is informational only.

For non-solar meters: `seg_earnings_gbp = 0.0`, `net_cost_gbp = annual_cost_gbp`.

The CSV `fields` list in `main()` gains `seg_earnings_gbp` and `net_cost_gbp`.

## Section 4: Tests

### `tests/test_tier1_lib.py` — new solar tests

- `test_load_solar_generation_returns_empty_for_non_solar_meter`
- `test_compute_annual_export_zero_when_no_generation`
- `test_compute_annual_export_clips_at_zero_when_consumption_exceeds_generation`
- `test_compute_annual_export_scales_to_annual`

### `tests/test_s01_tariff_matching.py` — new SEG tests

- `test_seg_earnings_present_in_output_rows` — both `seg_earnings_gbp` and `net_cost_gbp` keys exist
- `test_net_cost_equals_annual_minus_seg` — `net_cost_gbp == annual_cost_gbp - seg_earnings_gbp` for every row
- `test_seg_earnings_zero_for_non_solar_meter` — non-solar meter produces `seg_earnings_gbp = 0.0`

Existing tests require no changes — new columns are purely additive.

## Files Changed

| File | Change |
|---|---|
| `py/config.py` | Add `SOLAR_METERS`, `SEG_RATE_P_KWH` |
| `py/tier1_lib.py` | Add `load_solar_generation()`, `compute_annual_export()` |
| `py/s01_tariff_matching.py` | Import new functions, compute SEG earnings, add columns |
| `app.py` | Extend `_consumption_summary()` for solar columns |
| `tests/test_tier1_lib.py` | Add solar function tests |
| `tests/test_s01_tariff_matching.py` | Add SEG column tests |

## Out of Scope

- S02 battery sizing does not change in this spec (solar-aware battery optimisation is a follow-on)
- No per-tariff export modelling — SEG rate is constant across all tariffs
- M2's anomalous early-2023 data spike is not filtered here — that is a data quality issue to address separately

# Optimum Solar + Battery Sizing — Design Spec

**Date:** 2026-07-17  
**Status:** Approved

---

## Goal

Given a metered electricity usage pattern and the existing panel × battery sweep in `solar_analysis.py`, identify and report the single configuration with the shortest payback period across all profiles and battery configs.

---

## Scope

- Add one function `find_optimum()` to `solar_analysis.py`
- Call it from `main()` after the sweep completes
- Append the result to the existing text output (stdout + results file)
- No new files, no changes to sweep logic, no changes to existing tests

---

## Function: `find_optimum(all_results)`

**Location:** `solar_analysis.py`

**Signature:**
```python
def find_optimum(all_results: dict) -> dict | None
```

**Input:**  
`all_results` — the dict already built in `main()`:  
`{(profile_label, config_label): (savings_2d, paybacks_2d)}`  
where `savings_2d` and `paybacks_2d` are numpy arrays shaped `(len(PANEL_SIZES_KWP), len(BATTERY_SIZES_KWH))`.

**Logic:**
1. Iterate all `(profile_label, config_label)` keys and all `(pi, bi)` index pairs
2. Skip cells where `payback == inf` (annual saving ≤ 0)
3. Track the global minimum finite payback
4. Tie-break: if two cells share the same minimum payback, prefer the one with higher annual saving
5. Return a result dict (see below), or `None` if no viable cell exists

**Return dict keys:**
```python
{
    "profile":           str,    # e.g. "PVGIS"
    "config_label":      str,    # e.g. "0.5C"
    "panel_kwp":         float,  # from PANEL_SIZES_KWP[pi]
    "battery_kwh":       float,  # from BATTERY_SIZES_KWH[bi]
    "payback_years":     float,
    "annual_saving_gbp": float,
    "installed_cost_gbp": float, # panel_kwp * SOLAR_COST_PER_KWP + battery_kwh * BATTERY_COST_PER_KWH
}
```

---

## Output block

`main()` calls `find_optimum(all_results)` after the sweep loop and before heatmaps. The result is appended to `lines` (and thus to both stdout and the results file).

**Format (viable result):**
```
RECOMMENDED SYSTEM (shortest payback, all profiles and configs)
  Profile:        PVGIS
  Battery config: 0.5C  (RTE 92%, max 0.5C)
  Solar panels:   6 kWp   —  £5,400 installed
  Battery:        5 kWh   —  £2,500 installed
  Total cost:     £7,900
  Annual saving:  £951/yr
  Payback:        8.3 years
```

The RTE and max_c_rate values are looked up from `BATTERY_CONFIGS` by matching `config_label`.

**Format (no viable result):**
```
RECOMMENDED SYSTEM: No configuration yields a positive annual saving.
```

---

## Integration point in `main()`

Insert after:
```python
    for profile_label, solar_profile in profiles:
        for config in BATTERY_CONFIGS:
            ...
            all_results[...] = (savings, paybacks)
            lines.extend(build_text_table(...))
            lines.append("")
```

Add:
```python
    optimum = find_optimum(all_results)
    lines.extend(build_optimum_block(optimum))
    lines.append("")
```

`build_optimum_block(optimum)` is a small helper that formats the output lines (keeps `find_optimum` pure / testable and `main()` readable).

---

## Testing

No new test file. The function is deterministic and exercisable via a synthetic `all_results` dict in `tests/test_solar_battery_simulator.py` or a new `tests/test_solar_analysis.py`. This is optional — the logic is a single argmin with a tie-break and is trivially verified by inspection.

# Optimum Solar + Battery Sizing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `find_optimum()` and `build_optimum_block()` to `solar_analysis.py` to identify and print the single solar + battery configuration with the shortest payback period across all sweep results.

**Architecture:** Two pure functions added to `solar_analysis.py` — `find_optimum()` searches the existing `all_results` dict for the minimum finite payback (tie-breaking on highest annual saving), `build_optimum_block()` formats the output lines. `main()` calls both after the sweep loop and before heatmap generation. One new test file covers both functions with synthetic data.

**Tech Stack:** Python, numpy (already imported in `solar_analysis.py`), pytest.

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `solar_analysis.py` | Modify | Add `find_optimum()`, `build_optimum_block()`, wire into `main()` |
| `tests/test_solar_analysis.py` | Create | Unit tests for both new functions |

---

### Task 1: Write failing tests for `find_optimum()`

**Files:**
- Create: `tests/test_solar_analysis.py`

- [ ] **Step 1: Create the test file with failing tests**

```python
import numpy as np
import pytest
from solar_analysis import find_optimum, PANEL_SIZES_KWP, BATTERY_SIZES_KWH


def _make_results(payback_map):
    """
    Build a synthetic all_results dict.
    payback_map: {(profile, config): list[list[payback]]}
    Savings are derived as installed_cost / payback (or 0 for inf).
    SOLAR_COST_PER_KWP=900, BATTERY_COST_PER_KWH=500 match solar_analysis.py constants.
    """
    results = {}
    n_p = len(PANEL_SIZES_KWP)
    n_b = len(BATTERY_SIZES_KWH)
    for key, pb_grid in payback_map.items():
        paybacks = np.array(pb_grid, dtype=float)
        savings = np.zeros((n_p, n_b))
        for pi, panel_kwp in enumerate(PANEL_SIZES_KWP):
            for bi, battery_kwh in enumerate(BATTERY_SIZES_KWH):
                p = paybacks[pi][bi]
                installed = panel_kwp * 900 + battery_kwh * 500
                savings[pi][bi] = installed / p if p < np.inf else 0.0
        results[key] = (savings, paybacks)
    return results


def test_find_optimum_returns_shortest_payback():
    """Single profile/config, clear winner at (pi=0, bi=1) — 2 kWp, 2 kWh."""
    n_p = len(PANEL_SIZES_KWP)   # 6
    n_b = len(BATTERY_SIZES_KWH)  # 7
    pb_grid = [[np.inf] * n_b for _ in range(n_p)]
    pb_grid[0][1] = 8.0   # 2 kWp, 2 kWh → 8 years (best)
    pb_grid[1][2] = 10.0  # 4 kWp, 5 kWh → 10 years

    results = _make_results({("PVGIS", "0.5C"): pb_grid})
    opt = find_optimum(results)

    assert opt is not None
    assert opt["profile"] == "PVGIS"
    assert opt["config_label"] == "0.5C"
    assert opt["panel_kwp"] == PANEL_SIZES_KWP[0]   # 2
    assert opt["battery_kwh"] == BATTERY_SIZES_KWH[1]  # 2
    assert opt["payback_years"] == pytest.approx(8.0)


def test_find_optimum_tie_break_prefers_higher_saving():
    """Two cells share same payback — pick the one with higher annual saving."""
    n_p = len(PANEL_SIZES_KWP)
    n_b = len(BATTERY_SIZES_KWH)
    pb_grid = [[np.inf] * n_b for _ in range(n_p)]
    # (pi=0, bi=1): 2 kWp, 2 kWh — small installed cost → low saving
    # (pi=2, bi=2): 6 kWp, 5 kWh — large installed cost → higher saving
    # Force same payback by setting paybacks equal
    pb_grid[0][1] = 9.0
    pb_grid[2][2] = 9.0

    results = _make_results({("PVGIS", "0.5C"): pb_grid})
    opt = find_optimum(results)

    # 6 kWp + 5 kWh: installed = 6*900 + 5*500 = 7900 → saving = 7900/9 ≈ 877.8
    # 2 kWp + 2 kWh: installed = 2*900 + 2*500 = 2800 → saving = 2800/9 ≈ 311.1
    assert opt["panel_kwp"] == PANEL_SIZES_KWP[2]   # 6
    assert opt["battery_kwh"] == BATTERY_SIZES_KWH[2]  # 5


def test_find_optimum_across_multiple_profiles_and_configs():
    """Winner comes from a non-first profile/config combination."""
    n_p = len(PANEL_SIZES_KWP)
    n_b = len(BATTERY_SIZES_KWH)

    def full_inf():
        return [[np.inf] * n_b for _ in range(n_p)]

    pvgis_05 = full_inf(); pvgis_05[1][1] = 12.0
    pvgis_1c = full_inf(); pvgis_1c[2][2] = 11.0
    meas_05  = full_inf(); meas_05[3][3]  = 7.5   # ← global winner
    meas_1c  = full_inf(); meas_1c[4][4]  = 9.0

    results = _make_results({
        ("PVGIS", "0.5C"): pvgis_05,
        ("PVGIS", "1C"):   pvgis_1c,
        ("Measured", "0.5C"): meas_05,
        ("Measured", "1C"):   meas_1c,
    })
    opt = find_optimum(results)

    assert opt["profile"] == "Measured"
    assert opt["config_label"] == "0.5C"
    assert opt["payback_years"] == pytest.approx(7.5)


def test_find_optimum_all_inf_returns_none():
    """No viable configuration → returns None."""
    n_p = len(PANEL_SIZES_KWP)
    n_b = len(BATTERY_SIZES_KWH)
    pb_grid = [[np.inf] * n_b for _ in range(n_p)]
    results = _make_results({("PVGIS", "0.5C"): pb_grid})
    assert find_optimum(results) is None
```

- [ ] **Step 2: Run tests to confirm they all fail**

```bash
pytest tests/test_solar_analysis.py -v
```

Expected: 4 errors — `ImportError: cannot import name 'find_optimum' from 'solar_analysis'`

---

### Task 2: Implement `find_optimum()` in `solar_analysis.py`

**Files:**
- Modify: `solar_analysis.py` (insert after `run_sweep`, before `build_text_table`)

- [ ] **Step 1: Add `find_optimum()` after the `run_sweep` function (line ~113)**

Insert this block between `run_sweep` and `build_text_table`:

```python
def find_optimum(all_results):
    best = None
    for (profile_label, config_label), (savings, paybacks) in all_results.items():
        for pi, panel_kwp in enumerate(PANEL_SIZES_KWP):
            for bi, battery_kwh in enumerate(BATTERY_SIZES_KWH):
                p = paybacks[pi][bi]
                s = savings[pi][bi]
                if not np.isfinite(p):
                    continue
                if best is None or p < best["payback_years"] or (
                    p == best["payback_years"] and s > best["annual_saving_gbp"]
                ):
                    installed = panel_kwp * SOLAR_COST_PER_KWP + battery_kwh * BATTERY_COST_PER_KWH
                    best = {
                        "profile": profile_label,
                        "config_label": config_label,
                        "panel_kwp": panel_kwp,
                        "battery_kwh": battery_kwh,
                        "payback_years": p,
                        "annual_saving_gbp": s,
                        "installed_cost_gbp": installed,
                    }
    return best
```

- [ ] **Step 2: Run the tests — expect 4 passing**

```bash
pytest tests/test_solar_analysis.py -v
```

Expected output:
```
test_solar_analysis.py::test_find_optimum_returns_shortest_payback PASSED
test_solar_analysis.py::test_find_optimum_tie_break_prefers_higher_saving PASSED
test_solar_analysis.py::test_find_optimum_across_multiple_profiles_and_configs PASSED
test_solar_analysis.py::test_find_optimum_all_inf_returns_none PASSED
4 passed
```

- [ ] **Step 3: Commit**

```bash
git add solar_analysis.py tests/test_solar_analysis.py
git commit -m "feat: add find_optimum() to select shortest-payback solar+battery config"
```

---

### Task 3: Implement `build_optimum_block()` and wire into `main()`

**Files:**
- Modify: `solar_analysis.py`

- [ ] **Step 1: Add `build_optimum_block()` after `find_optimum()`**

```python
def build_optimum_block(optimum):
    if optimum is None:
        return ["RECOMMENDED SYSTEM: No configuration yields a positive annual saving."]

    cfg = next(c for c in BATTERY_CONFIGS if c["label"] == optimum["config_label"])
    panel_cost = optimum["panel_kwp"] * SOLAR_COST_PER_KWP
    battery_cost = optimum["battery_kwh"] * BATTERY_COST_PER_KWH

    return [
        "RECOMMENDED SYSTEM (shortest payback, all profiles and configs)",
        f"  Profile:        {optimum['profile']}",
        f"  Battery config: {optimum['config_label']}  "
        f"(RTE {cfg['rte']*100:.0f}%, max {cfg['max_c_rate']}C)",
        f"  Solar panels:   {optimum['panel_kwp']} kWp   —  "
        f"£{panel_cost:,.0f} installed",
        f"  Battery:        {optimum['battery_kwh']} kWh   —  "
        f"£{battery_cost:,.0f} installed",
        f"  Total cost:     £{optimum['installed_cost_gbp']:,.0f}",
        f"  Annual saving:  £{optimum['annual_saving_gbp']:,.0f}/yr",
        f"  Payback:        {optimum['payback_years']:.1f} years",
    ]
```

- [ ] **Step 2: Wire into `main()` — insert after the sweep loop, before heatmap generation**

In `main()`, locate this block (around line 397–399):
```python
    output = "\n".join(lines)
    print(output)
    with open(OUTPUT_FILE, "w") as f:
```

Insert before it:
```python
    optimum = find_optimum(all_results)
    lines.extend(build_optimum_block(optimum))
    lines.append("")
```

So the relevant section of `main()` becomes:
```python
    for profile_label, solar_profile in profiles:
        for config in BATTERY_CONFIGS:
            print(f"Sweeping {profile_label} / {config['label']}...")
            savings, paybacks = run_sweep(days, solar_profile, config)
            all_results[(profile_label, config["label"])] = (savings, paybacks)
            lines.extend(build_text_table(days, savings, paybacks, profile_label, config))
            lines.append("")

    optimum = find_optimum(all_results)
    lines.extend(build_optimum_block(optimum))
    lines.append("")

    output = "\n".join(lines)
    print(output)
    with open(OUTPUT_FILE, "w") as f:
        f.write(output + "\n")
    print(f"\nResults saved to {OUTPUT_FILE}")
```

- [ ] **Step 3: Run all existing tests to confirm nothing broken**

```bash
pytest -v
```

Expected: all previously passing tests still pass, plus the 4 new ones.

- [ ] **Step 4: Commit**

```bash
git add solar_analysis.py
git commit -m "feat: add build_optimum_block() and wire recommendation into main() output"
```

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

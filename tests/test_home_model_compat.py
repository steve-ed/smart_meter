"""
Verify that home_model.py public symbols are unchanged after the energy_model refactor.
tier4_analysis.py and app.py import DWELLING_PARAMS and build_dwelling directly.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'py'))

from home_model import DWELLING_PARAMS, build_dwelling


def test_dwelling_params_has_all_meters():
    """Meters 1-5 must be present (plus 6-15 for completeness)."""
    for m in range(1, 6):
        assert m in DWELLING_PARAMS, f"meter {m} missing from DWELLING_PARAMS"


def test_dwelling_params_meter1_values():
    p = DWELLING_PARAMS[1]
    assert p["total_floor_area_m2"] == 85.0
    assert p["u_wall"] == 0.60
    assert p["q50"] == 10.0
    assert p["label"] == "1970s semi, unimproved"


def test_build_dwelling_returns_htc():
    d = build_dwelling(DWELLING_PARAMS[1])
    assert "htc" in d
    assert d["htc"] > 0


def test_build_dwelling_returns_tau():
    d = build_dwelling(DWELLING_PARAMS[1])
    assert "tau_hours" in d
    assert d["tau_hours"] > 0


def test_build_dwelling_returns_c_wh_k():
    """tier4_analysis.py uses the key 'c_wh_k' (old name)."""
    d = build_dwelling(DWELLING_PARAMS[1])
    assert "c_wh_k" in d
    assert abs(d["c_wh_k"] - 160 * 85.0) < 0.1


def test_build_dwelling_meter1_htc_matches_spec():
    """HTC should be ~225 W/K for meter 1 per docs/home_model.md worked example."""
    d = build_dwelling(DWELLING_PARAMS[1])
    assert abs(d["htc"] - 225.1) < 2.0

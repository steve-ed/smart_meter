# tests/test_occupancy_elec.py
import pytest
from occupancy_elec import compute_floor, is_heating_contaminated, compute_thresholds


def test_compute_floor_returns_p20():
    # 10 values sorted: [0.02,0.02,0.03,0.04,0.05,0.06,0.10,0.15,0.20,0.30]
    # P20 = index int(10*0.20)=2 → 0.03
    samples = [0.02, 0.02, 0.03, 0.04, 0.05, 0.06, 0.10, 0.15, 0.20, 0.30]
    floor, _ = compute_floor(samples)
    assert floor == pytest.approx(0.03)


def test_compute_floor_mad_minimum_enforced():
    # All identical → raw MAD = 0 → clamped to 0.005
    floor, mad = compute_floor([0.05] * 20)
    assert mad == pytest.approx(0.005)


def test_compute_floor_mad_reflects_spread():
    samples = [0.02, 0.02, 0.03, 0.04, 0.05, 0.06, 0.10, 0.15, 0.20, 0.30]
    _, mad = compute_floor(samples)
    assert mad > 0.005


def test_compute_floor_empty_returns_zeros():
    floor, mad = compute_floor([])
    assert floor == 0.0
    assert mad == 0.0


def test_compute_floor_single_value():
    floor, mad = compute_floor([0.04])
    assert floor == pytest.approx(0.04)
    assert mad == pytest.approx(0.005)


# --- is_heating_contaminated ---


def test_heating_contaminated_when_both_conditions_met():
    assert is_heating_contaminated(0.6, 5.0) is True


def test_heating_not_contaminated_warm_outdoor():
    # outdoor temp above threshold → not contaminated even with high load
    assert is_heating_contaminated(0.6, 8.0) is False


def test_heating_not_contaminated_low_overnight_load():
    # load below threshold → not contaminated even when cold
    assert is_heating_contaminated(0.4, 5.0) is False


def test_heating_not_contaminated_at_exact_boundaries():
    # strictly greater / strictly less required — boundary values are not contaminated
    assert is_heating_contaminated(0.50, 7.0) is False


# --- compute_thresholds ---

def test_compute_thresholds_minimum_excess_dominates():
    # floor_mad = 0.005 → 3×MAD = 0.015 < 0.05, so hard = floor + 0.05
    hard, soft = compute_thresholds(floor_kwh=0.03, floor_mad=0.005)
    assert hard == pytest.approx(0.03 + 0.05)    # 0.08
    assert soft == pytest.approx(0.03 + 0.025)   # 0.055


def test_compute_thresholds_mad_dominates():
    # floor_mad = 0.02 → 3×MAD = 0.06 > 0.05
    hard, soft = compute_thresholds(floor_kwh=0.03, floor_mad=0.02)
    assert hard == pytest.approx(0.03 + 0.06)    # 0.09
    assert soft == pytest.approx(0.03 + 0.03)    # 0.06


def test_compute_thresholds_hard_always_exceeds_soft():
    for mad in [0.005, 0.01, 0.02, 0.05]:
        hard, soft = compute_thresholds(floor_kwh=0.05, floor_mad=mad)
        assert hard > soft, f"hard {hard} should exceed soft {soft} at mad={mad}"

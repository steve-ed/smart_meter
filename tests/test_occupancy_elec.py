# tests/test_occupancy_elec.py
import pytest
from occupancy_elec import compute_floor


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

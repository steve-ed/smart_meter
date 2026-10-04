import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py"))
import pytest
from solar_gains import compute_orientation_irradiance, surface_irradiance_w_per_m2


def test_surface_irradiance_south_positive_at_solar_noon_winter():
    """South-facing surface should have positive irradiance at January solar noon."""
    irr = surface_irradiance_w_per_m2("2024-01-15 12:00")
    assert irr > 50.0, f"Expected >50 W/m² south at noon in January, got {irr:.1f}"


def test_surface_irradiance_north_zero_at_noon():
    """North-facing surface receives no direct beam at solar noon — only diffuse sky scatter."""
    irr = surface_irradiance_w_per_m2("2024-01-15 12:00", orientation="N")
    assert irr == pytest.approx(0.0, abs=10.0)


def test_surface_irradiance_zero_at_night():
    """No irradiance at 2am."""
    irr = surface_irradiance_w_per_m2("2024-01-15 02:00")
    assert irr == pytest.approx(0.0)


def test_south_winter_noon_exceeds_summer_noon():
    """South-facing vertical irradiance should be higher in winter than summer at noon."""
    winter = surface_irradiance_w_per_m2("2024-01-15 12:00")
    summer = surface_irradiance_w_per_m2("2024-07-15 12:00")
    assert winter > summer, "South-vertical should peak in winter for UK latitude"


def test_compute_orientation_irradiance_returns_all_orientations():
    timestamps = ["2024-01-15 12:00", "2024-01-15 12:30"]
    result = compute_orientation_irradiance(timestamps, {"N": 0.2, "S": 0.5, "E": 0.15, "W": 0.15})
    assert "2024-01-15 12:00" in result
    assert set(result["2024-01-15 12:00"].keys()) == {"N", "S", "E", "W"}


def test_compute_orientation_irradiance_south_positive_noon():
    result = compute_orientation_irradiance(["2024-01-15 12:00"], {"S": 1.0})
    assert result["2024-01-15 12:00"]["S"] > 50.0


def test_compute_orientation_irradiance_zero_at_night():
    result = compute_orientation_irradiance(["2024-01-15 02:00"], {"S": 1.0, "N": 1.0})
    assert result["2024-01-15 02:00"]["S"] == pytest.approx(0.0)
    assert result["2024-01-15 02:00"]["N"] == pytest.approx(0.0)

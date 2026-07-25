import pytest
from s08_carbon_shifting import optimal_shift_window


def _carbon(intensities: list[float]) -> list[dict]:
    return [
        {"period_index": i, "intensity_gco2": v}
        for i, v in enumerate(intensities)
    ]

def _load(min_periods=2, earliest=0, latest=5):
    return {
        "appliance":       "washing_machine",
        "typical_kwh":     1.0,
        "min_periods":     min_periods,
        "earliest_period": earliest,
        "latest_period":   latest,
    }


def test_finds_lowest_carbon_window():
    intensities = [200, 180, 160, 80, 90, 170, 200, 200]
    result = optimal_shift_window(_carbon(intensities), _load(min_periods=2, earliest=0, latest=7))
    assert result["recommended_start_period"] == 3

def test_window_respects_earliest_latest():
    intensities = [50, 50, 200, 200, 200, 200]
    result = optimal_shift_window(_carbon(intensities), _load(min_periods=2, earliest=2, latest=5))
    assert result["recommended_start_period"] >= 2

def test_insufficient_window():
    intensities = [200, 200]
    result = optimal_shift_window(_carbon(intensities), _load(min_periods=3, earliest=0, latest=1))
    assert result["recommendation"] is None

def test_carbon_saving_computed():
    intensities = [200] * 4 + [100] * 4
    result = optimal_shift_window(_carbon(intensities), _load(min_periods=2, earliest=0, latest=7))
    assert result["carbon_saving_gco2"] > 0

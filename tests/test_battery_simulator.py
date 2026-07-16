import pytest
from battery_simulator import simulate_day


def test_no_saving_when_no_peak_slots():
    """Single rate means no arbitrage opportunity — saving is zero."""
    consumption_hh = [0.5] * 48
    tariff_hh = [8.78] * 48
    result = simulate_day(consumption_hh, tariff_hh, battery_capacity_kwh=5.0,
                          round_trip_efficiency=1.0, max_c_rate=0.5, min_soc=0.0)
    assert result["daily_saving_p"] == pytest.approx(0.0)
    assert result["peak_kwh_displaced"] == pytest.approx(0.0)


def test_battery_charges_and_saves_during_peak():
    """
    5 kWh battery, efficiency=1, min_soc=0.
    24 off-peak then 24 peak slots, consumption 1.0 kWh/slot.
    max per slot = 5 * 0.5 * 0.5 = 1.25 kWh.
    Charges to full in 4 off-peak slots (4 * 1.25 = 5.0 kWh).
    Discharges 1.0 kWh/slot for 5 peak slots until empty.
    Total delivered = 5.0 kWh.
    Saving = 5.0 * (16.29 - (8.78 / 1.0)) = 5.0 * 7.51 = 37.55p.
    """
    consumption_hh = [1.0] * 48
    tariff_hh = [8.78] * 24 + [16.29] * 24
    result = simulate_day(consumption_hh, tariff_hh, battery_capacity_kwh=5.0,
                          round_trip_efficiency=1.0, max_c_rate=0.5, min_soc=0.0)
    assert result["daily_saving_p"] == pytest.approx(37.55, rel=1e-3)
    assert result["peak_kwh_displaced"] == pytest.approx(5.0, rel=1e-3)


def test_small_battery_partial_displacement():
    """
    2 kWh battery, efficiency=1, min_soc=0.
    max per slot = 2 * 0.5 * 0.5 = 0.5 kWh.
    Charges to full in 4 off-peak slots (4 * 0.5 = 2.0 kWh).
    Discharges 0.5 kWh/slot for 4 peak slots.
    Total delivered = 2.0 kWh.
    Saving = 2.0 * (16.29 - (8.78 / 1.0)) = 2.0 * 7.51 = 15.02p.
    """
    consumption_hh = [1.0] * 48
    tariff_hh = [8.78] * 24 + [16.29] * 24
    result = simulate_day(consumption_hh, tariff_hh, battery_capacity_kwh=2.0,
                          round_trip_efficiency=1.0, max_c_rate=0.5, min_soc=0.0)
    assert result["daily_saving_p"] == pytest.approx(15.02, rel=1e-3)
    assert result["peak_kwh_displaced"] == pytest.approx(2.0, rel=1e-3)


def test_large_battery_capped_by_consumption():
    """
    20 kWh battery, efficiency=1, min_soc=0, consumption only 0.1 kWh/slot.
    max per slot = 20 * 0.5 * 0.5 = 5.0 kWh >> consumption.
    Battery easily fills; during peak discharges exactly 0.1 kWh/slot.
    Total delivered = 24 * 0.1 = 2.4 kWh.
    Saving = 2.4 * (16.29 - (8.78 / 1.0)) = 2.4 * 7.51 = 18.024p.
    """
    consumption_hh = [0.1] * 48
    tariff_hh = [8.78] * 24 + [16.29] * 24
    result = simulate_day(consumption_hh, tariff_hh, battery_capacity_kwh=20.0,
                          round_trip_efficiency=1.0, max_c_rate=0.5, min_soc=0.0)
    assert result["daily_saving_p"] == pytest.approx(18.024, rel=1e-3)
    assert result["peak_kwh_displaced"] == pytest.approx(2.4, rel=1e-3)


def test_round_trip_efficiency_reduces_saving():
    """
    Round-trip loss means more must be drawn from battery than is delivered.
    5 kWh battery, efficiency=0.9, min_soc=0.
    max_hh_kwh = 5 * 0.5 * 0.5 = 1.25 kWh.
    draw per slot = min(1.25, available, consumption / 0.9) = min(1.25, soc, 1.111).
    Slot 24: draw=1.111, delivered=1.0, soc=3.889
    Slot 25: draw=1.111, delivered=1.0, soc=2.778
    Slot 26: draw=1.111, delivered=1.0, soc=1.667
    Slot 27: draw=1.111, delivered=1.0, soc=0.556
    Slot 28: draw=0.556, delivered=0.500, soc=0.0
    Total delivered = 4.5 kWh.
    Saving = 4.5 * (16.29 - (8.78 / 0.9)) = 4.5 * 6.534 = 29.40p.
    """
    consumption_hh = [1.0] * 48
    tariff_hh = [8.78] * 24 + [16.29] * 24
    result = simulate_day(consumption_hh, tariff_hh, battery_capacity_kwh=5.0,
                          round_trip_efficiency=0.9, max_c_rate=0.5, min_soc=0.0)
    assert result["daily_saving_p"] == pytest.approx(29.40, rel=1e-2)
    assert result["peak_kwh_displaced"] == pytest.approx(4.5, rel=1e-2)

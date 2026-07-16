import pytest
from solar_battery_simulator import simulate_day_solar


def test_no_solar_no_battery_zero_saving():
    """No solar, no battery → cost equals baseline, saving = 0."""
    consumption = [0.5] * 48
    tariff = [8.78] * 24 + [16.29] * 24
    solar = [0.0] * 48
    result = simulate_day_solar(
        consumption, tariff, solar,
        battery_capacity_kwh=0,
        round_trip_efficiency=1.0,
        max_c_rate=0.5,
        min_soc=0.0,
        export_rate_p=0.0,
    )
    assert result["daily_saving_p"] == pytest.approx(0.0)
    assert result["solar_self_consumed_kwh"] == pytest.approx(0.0)
    assert result["solar_exported_kwh"] == pytest.approx(0.0)
    assert result["peak_kwh_displaced"] == pytest.approx(0.0)


def test_solar_self_consumption_and_export_no_battery():
    """
    Solar 1.0 kWh/slot off-peak only, consumption 0.5 kWh/slot, no battery.
    Off-peak (8.78p): self-consumed 0.5, exported 0.5
    Peak (16.29p): no solar, grid covers 0.5

    baseline  = 24*0.5*8.78 + 24*0.5*16.29 = 105.36 + 195.48 = 300.84p
    grid_cost = 0          + 24*0.5*16.29  = 195.48p
    export_rev= 24*0.5*15  = 180p
    saving    = 300.84 - 195.48 + 180 = 285.36p
    """
    consumption = [0.5] * 48
    tariff = [8.78] * 24 + [16.29] * 24
    solar = [1.0] * 24 + [0.0] * 24
    result = simulate_day_solar(
        consumption, tariff, solar,
        battery_capacity_kwh=0,
        round_trip_efficiency=1.0,
        max_c_rate=0.5,
        min_soc=0.0,
        export_rate_p=15.0,
    )
    assert result["daily_saving_p"] == pytest.approx(285.36, rel=1e-4)
    assert result["solar_self_consumed_kwh"] == pytest.approx(12.0)
    assert result["solar_exported_kwh"] == pytest.approx(12.0)
    assert result["peak_kwh_displaced"] == pytest.approx(0.0)


def test_solar_charges_battery_then_discharges_at_peak():
    """
    Off-peak (8.78p): consumption 0, solar 1.0 → charges 5kWh battery then exports rest.
    Peak (16.29p): consumption 0.5 kWh/slot, no solar → battery covers first 10 slots.

    Off-peak: 4 slots to fill battery (1.0 solar + 0.25 grid each = 1.25 total per slot)
              → battery full at soc=5.0 after slot 3
              → slots 4-23: solar exported, no grid draw (consumption=0)
    Grid cost off-peak: 4 slots × 0.25 × 8.78 = 8.78p

    Peak: battery has 5.0 kWh, draw min(1.25, soc, 0.5/1.0)=0.5 per slot × 10 slots
          → soc=0 after slot 33; slots 34-47 from grid: 14 × 0.5 × 16.29 = 114.03p

    baseline  = 24*0*8.78 + 24*0.5*16.29 = 195.48p
    grid_cost = 8.78 + 114.03 = 122.81p
    export_rev= 20 * 0 = 0 (export_rate=0)
    saving    = 195.48 - 122.81 = 72.67p
    """
    consumption = [0.0] * 24 + [0.5] * 24
    tariff = [8.78] * 24 + [16.29] * 24
    solar = [1.0] * 24 + [0.0] * 24
    result = simulate_day_solar(
        consumption, tariff, solar,
        battery_capacity_kwh=5.0,
        round_trip_efficiency=1.0,
        max_c_rate=0.5,
        min_soc=0.0,
        export_rate_p=0.0,
    )
    assert result["daily_saving_p"] == pytest.approx(72.67, rel=1e-3)
    assert result["solar_self_consumed_kwh"] == pytest.approx(0.0)
    assert result["solar_exported_kwh"] == pytest.approx(20.0)
    assert result["peak_kwh_displaced"] == pytest.approx(5.0)


def test_no_solar_battery_only_matches_battery_simulator():
    """
    With solar=0, simulate_day_solar should give the same result as battery_simulator.simulate_day.
    5kWh battery, rte=1.0, consumption=1.0, 2-rate tariff, min_soc=0.
    Charges 4 slots × 1.25 = 5 kWh off-peak. Discharges 5 slots × 1.0 at peak.
    saving = 5 * (16.29 - 8.78) = 37.55p
    """
    consumption = [1.0] * 48
    tariff = [8.78] * 24 + [16.29] * 24
    solar = [0.0] * 48
    result = simulate_day_solar(
        consumption, tariff, solar,
        battery_capacity_kwh=5.0,
        round_trip_efficiency=1.0,
        max_c_rate=0.5,
        min_soc=0.0,
        export_rate_p=0.0,
    )
    assert result["daily_saving_p"] == pytest.approx(37.55, rel=1e-3)
    assert result["peak_kwh_displaced"] == pytest.approx(5.0)

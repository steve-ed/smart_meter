import pytest
from tier1_lib import (
    build_weekly_profile,
    consumption_shape,
    rate_for_period,
    annual_cost_for_tariff,
)


# --- build_weekly_profile ---

def _make_readings(weekday, period, kwh, n=10):
    return [{"weekday": weekday, "period_index": period, "elec_kwh": kwh}] * n

def test_profile_returns_median():
    readings = _make_readings(0, 0, 1.0, 5) + _make_readings(0, 0, 3.0, 5)
    profile = build_weekly_profile(readings, weeks=999)
    assert profile[(0, 0)] == pytest.approx(2.0)

def test_profile_groups_by_weekday_and_period():
    readings = (
        [{"weekday": 0, "period_index": 0, "elec_kwh": 1.0}] * 5 +
        [{"weekday": 1, "period_index": 0, "elec_kwh": 2.0}] * 5
    )
    profile = build_weekly_profile(readings, weeks=999)
    assert profile[(0, 0)] == pytest.approx(1.0)
    assert profile[(1, 0)] == pytest.approx(2.0)

def test_profile_empty_readings():
    assert build_weekly_profile([], weeks=8) == {}


# --- consumption_shape ---

def _flat_profile(kwh=1.0):
    return {(wd, p): kwh for wd in range(7) for p in range(48)}

def test_shape_night_fraction():
    profile = _flat_profile()
    shape = consumption_shape(profile)
    # night = periods 0-13 (14 periods per day * 7 days = 98 slots)
    # total = 48 * 7 = 336 slots
    assert shape["night_fraction"] == pytest.approx(98 / 336, abs=0.001)

def test_shape_annual_kwh_estimate():
    profile = _flat_profile(1.0)
    shape = consumption_shape(profile)
    # weekly total = 336 kWh; annual = 336/7*365
    assert shape["annual_kwh_estimate"] == pytest.approx(336 / 7 * 365, abs=1.0)

def test_shape_empty_profile():
    shape = consumption_shape({})
    assert shape["annual_kwh_estimate"] == 0.0


# --- rate_for_period ---

def _bands(flat_rate=20.0):
    return [{"start_period": 0, "end_period": 47, "rate_p_per_kwh": flat_rate}]

def test_rate_for_period_flat():
    assert rate_for_period(_bands(20.0), 0) == pytest.approx(20.0)
    assert rate_for_period(_bands(20.0), 47) == pytest.approx(20.0)

def test_rate_for_period_two_rate():
    bands = [
        {"start_period": 0,  "end_period": 13, "rate_p_per_kwh": 7.5},
        {"start_period": 14, "end_period": 47, "rate_p_per_kwh": 24.5},
    ]
    assert rate_for_period(bands, 0)  == pytest.approx(7.5)
    assert rate_for_period(bands, 13) == pytest.approx(7.5)
    assert rate_for_period(bands, 14) == pytest.approx(24.5)
    assert rate_for_period(bands, 47) == pytest.approx(24.5)

def test_rate_for_period_no_match_raises():
    bands = [{"start_period": 10, "end_period": 20, "rate_p_per_kwh": 20.0}]
    with pytest.raises(ValueError):
        rate_for_period(bands, 5)


# --- annual_cost_for_tariff ---

def _readings_365(kwh=1.0):
    from datetime import date, timedelta
    base = date(2024, 1, 1)
    rows = []
    for i in range(365 * 48):
        d = base + timedelta(days=i // 48)
        period = i % 48
        rows.append({
            "timestamp": f"{d} {period//2:02d}:{(period%2)*30:02d}",
            "elec_kwh": kwh,
            "weekday": d.weekday(),
            "period_index": period,
        })
    return rows

def test_annual_cost_flat_tariff():
    readings = _readings_365(1.0)   # 1 kWh per period, 48 per day
    bands = [{"start_period": 0, "end_period": 47, "rate_p_per_kwh": 20.0}]
    result = annual_cost_for_tariff(readings, bands, standing_p_day=50.0)
    # unit: 365 days * 48 periods * 1 kWh * 20p = 350,400p = £3,504
    # standing: 365 * 50p = £182.50
    assert result["unit_cost_gbp"] == pytest.approx(3504.0, abs=1.0)
    assert result["standing_cost_gbp"] == pytest.approx(182.5, abs=0.1)
    assert result["total_cost_gbp"] == pytest.approx(3686.5, abs=1.0)
    assert result["days_in_sample"] == 365

def test_annual_cost_scales_short_sample():
    # 30 days of readings, should scale to 365
    from datetime import date, timedelta
    base = date(2024, 1, 1)
    readings = []
    for i in range(30 * 48):
        d = base + timedelta(days=i // 48)
        period = i % 48
        readings.append({
            "timestamp": f"{d} {period//2:02d}:{(period%2)*30:02d}",
            "elec_kwh": 1.0,
            "weekday": d.weekday(),
            "period_index": period,
        })
    bands = [{"start_period": 0, "end_period": 47, "rate_p_per_kwh": 20.0}]
    result = annual_cost_for_tariff(readings, bands, standing_p_day=0.0)
    # 30 days * 48 * 1 kWh * 20p = 28,800p, scaled * (365/30) = 350,400p = £3,504
    assert result["unit_cost_gbp"] == pytest.approx(3504.0, abs=5.0)
    assert result["days_in_sample"] == 30

import pytest
from s02_battery_sizing import build_daily_arrays, npv, find_recommended


# --- build_daily_arrays ---

def _readings(n_days=5, kwh=1.0):
    from datetime import date, timedelta
    base = date(2024, 1, 1)
    rows = []
    for i in range(n_days * 48):
        d = base + timedelta(days=i // 48)
        period = i % 48
        rows.append({
            "timestamp": f"{d} {period//2:02d}:{(period%2)*30:02d}",
            "elec_kwh": kwh,
            "weekday": d.weekday(),
            "period_index": period,
        })
    return rows

def _rates(cheap_p=7.5, dear_p=24.0):
    rates = {}
    for p in range(14):
        rates[p] = cheap_p
    for p in range(14, 48):
        rates[p] = dear_p
    return rates

def test_build_daily_arrays_length():
    readings = _readings(n_days=5)
    rates = _rates()
    arrays = build_daily_arrays(readings, rates)
    assert len(arrays) == 5

def test_build_daily_arrays_consumption_shape():
    readings = _readings(n_days=2, kwh=0.5)
    rates = _rates()
    arrays = build_daily_arrays(readings, rates)
    assert len(arrays[0][0]) == 48    # consumption list has 48 periods
    assert all(v == pytest.approx(0.5) for v in arrays[0][0])

def test_build_daily_arrays_tariff_shape():
    readings = _readings(n_days=2)
    rates = _rates(cheap_p=7.5, dear_p=24.0)
    arrays = build_daily_arrays(readings, rates)
    tariff_hh = arrays[0][1]
    assert tariff_hh[0] == pytest.approx(7.5)
    assert tariff_hh[14] == pytest.approx(24.0)

def test_build_daily_arrays_skips_incomplete_days():
    # Only 47 readings in first day → skip it
    from datetime import date, timedelta
    base = date(2024, 1, 1)
    readings = []
    for p in range(47):   # incomplete first day
        readings.append({"timestamp": f"{base} {p//2:02d}:{(p%2)*30:02d}",
                         "elec_kwh": 1.0, "weekday": 0, "period_index": p})
    d2 = base + timedelta(days=1)
    for p in range(48):
        readings.append({"timestamp": f"{d2} {p//2:02d}:{(p%2)*30:02d}",
                         "elec_kwh": 1.0, "weekday": 1, "period_index": p})
    arrays = build_daily_arrays(readings, {p: 20.0 for p in range(48)})
    assert len(arrays) == 1   # only the complete day


# --- npv ---

def test_npv_positive_saving():
    # £100/yr saving, £500 cost, 3.5% rate, 10 years
    result = npv(100.0, 500.0, rate=0.035, years=10)
    assert result == pytest.approx(100 * sum(1/1.035**t for t in range(1,11)) - 500, abs=0.01)

def test_npv_zero_saving_negative():
    result = npv(0.0, 500.0, rate=0.035, years=10)
    assert result == pytest.approx(-500.0)


# --- find_recommended ---

def test_find_recommended_shortest_payback():
    curve = [
        {"capacity_kwh": 2.0, "payback_years": 8.0,  "annual_saving_gbp": 100.0},
        {"capacity_kwh": 5.0, "payback_years": 12.0, "annual_saving_gbp": 200.0},
        {"capacity_kwh": 10.0,"payback_years": float("inf"), "annual_saving_gbp": 0.0},
    ]
    result = find_recommended(curve)
    assert result["capacity_kwh"] == 2.0

def test_find_recommended_ignores_inf_payback():
    curve = [
        {"capacity_kwh": 2.0, "payback_years": float("inf"), "annual_saving_gbp": 0.0},
        {"capacity_kwh": 5.0, "payback_years": 20.0, "annual_saving_gbp": 50.0},
    ]
    result = find_recommended(curve)
    assert result is None   # no payback <= 15 years

def test_find_recommended_none_when_all_inf():
    curve = [{"capacity_kwh": 5.0, "payback_years": float("inf"), "annual_saving_gbp": 0.0}]
    assert find_recommended(curve) is None

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


# --- load_solar_generation ---

def test_load_solar_generation_returns_empty_for_non_solar_meter(tmp_path):
    from tier1_lib import load_solar_generation
    # meter_id 99 is not in SOLAR_METERS
    result = load_solar_generation(99, path=str(tmp_path / "production_clean.csv"))
    assert result == []

def test_load_solar_generation_reads_rows_for_solar_meter(tmp_path):
    from tier1_lib import load_solar_generation
    import csv as _csv
    p = tmp_path / "production_clean.csv"
    with open(p, "w", newline="") as f:
        w = _csv.DictWriter(f, fieldnames=["mpxn","utility","reading_type","device_id","timestamp","value","unit"])
        w.writeheader()
        # M3 MPXN
        w.writerow({"mpxn":"5330642497188","utility":"electricity","reading_type":"production",
                    "device_id":"x","timestamp":"2024-06-01 12:00","value":"1.5","unit":"kWh"})
        w.writerow({"mpxn":"5330642497188","utility":"electricity","reading_type":"production",
                    "device_id":"x","timestamp":"2024-06-01 12:30","value":"2.0","unit":"kWh"})
        # Different meter — should be excluded
        w.writerow({"mpxn":"9999999999999","utility":"electricity","reading_type":"production",
                    "device_id":"x","timestamp":"2024-06-01 12:00","value":"5.0","unit":"kWh"})
    result = load_solar_generation(3, path=str(p))
    assert len(result) == 2
    assert result[0]["solar_kwh"] == pytest.approx(1.5, rel=0.001)
    assert result[1]["solar_kwh"] == pytest.approx(2.0, rel=0.001)
    assert result[0]["timestamp"] == "2024-06-01 12:00"
    assert result[0]["period_index"] == 24   # 12:00 → period 24


# --- compute_annual_export ---

def _make_consumption(timestamps_kwh: list[tuple[str, float]]) -> list[dict]:
    rows = []
    for ts, kwh in timestamps_kwh:
        from datetime import datetime as _dt
        d = _dt.strptime(ts, "%Y-%m-%d %H:%M")
        rows.append({
            "timestamp":    ts,
            "elec_kwh":     kwh,
            "weekday":      d.weekday(),
            "period_index": d.hour * 2 + d.minute // 30,
        })
    return rows

def _make_generation(timestamps_kwh: list[tuple[str, float]]) -> list[dict]:
    rows = []
    for ts, kwh in timestamps_kwh:
        from datetime import datetime as _dt
        d = _dt.strptime(ts, "%Y-%m-%d %H:%M")
        rows.append({
            "timestamp":    ts,
            "solar_kwh":    kwh,
            "period_index": d.hour * 2 + d.minute // 30,
        })
    return rows

def test_compute_annual_export_zero_when_no_generation():
    from tier1_lib import compute_annual_export
    consumption = _make_consumption([("2024-06-01 12:00", 1.0)])
    result = compute_annual_export(consumption, [])
    assert result["annual_export_kwh"] == 0.0
    assert result["annual_generation_kwh"] == 0.0

def test_compute_annual_export_clips_at_zero_when_consumption_exceeds_generation():
    from tier1_lib import compute_annual_export
    ts = "2024-06-01 12:00"
    consumption = _make_consumption([(ts, 2.0)])
    generation  = _make_generation([(ts, 0.5)])
    result = compute_annual_export(consumption, generation)
    assert result["annual_export_kwh"] == pytest.approx(0.0)

def test_compute_annual_export_correct_when_generation_exceeds_consumption():
    from tier1_lib import compute_annual_export
    ts = "2024-06-01 12:00"
    consumption = _make_consumption([(ts, 0.5)])
    generation  = _make_generation([(ts, 2.0)])
    result = compute_annual_export(consumption, generation)
    # export per period = 2.0 - 0.5 = 1.5 kWh; 1 day sample → scale × 365
    assert result["annual_export_kwh"] == pytest.approx(1.5 * 365, rel=0.01)
    assert result["annual_generation_kwh"] == pytest.approx(2.0 * 365, rel=0.01)

def test_compute_annual_export_scales_to_annual():
    from tier1_lib import compute_annual_export
    from datetime import date, timedelta
    base = date(2024, 6, 1)
    consumption = _make_consumption(
        [(f"{base + timedelta(days=i)} 12:00", 0.0) for i in range(30)]
    )
    generation = _make_generation(
        [(f"{base + timedelta(days=i)} 12:00", 1.0) for i in range(30)]
    )
    result = compute_annual_export(consumption, generation)
    assert result["annual_export_kwh"] == pytest.approx(365.0, rel=0.01)
    assert result["days_in_sample"] == 30

import pytest
from s01_tariff_matching import rank_alternatives, current_annual_cost, flag_too_close


def _readings(kwh_night=0.5, kwh_day=1.0, days=30):
    """Generate synthetic readings: 14 night periods + 34 day periods per day."""
    from datetime import date, timedelta
    base = date(2024, 11, 1)
    rows = []
    for i in range(days * 48):
        d = base + timedelta(days=i // 48)
        period = i % 48
        kwh = kwh_night if period <= 13 else kwh_day
        rows.append({
            "timestamp": f"{d} {period//2:02d}:{(period%2)*30:02d}",
            "elec_kwh": kwh,
            "weekday": d.weekday(),
            "period_index": period,
        })
    return rows


def _actual_rates():
    return {p: 24.0 for p in range(48)}, 50.0   # flat 24p, 50p/day standing


def _eon_products():
    return [
        {
            "name": "E.ON Next Fixed",
            "product_type": "flat",
            "standing_p_day": 50.0,
            "bands": [{"start_period": 0, "end_period": 47, "rate_p_per_kwh": 24.0}],
        },
        {
            "name": "E.ON Next Drive",
            "product_type": "two_rate",
            "standing_p_day": 50.0,
            "bands": [
                {"start_period": 0,  "end_period": 13, "rate_p_per_kwh": 7.5},
                {"start_period": 14, "end_period": 47, "rate_p_per_kwh": 24.5},
            ],
        },
    ]


# --- current_annual_cost ---

def test_current_annual_cost_returns_expected_fields():
    readings = _readings()
    period_rates, standing = _actual_rates()
    result = current_annual_cost(readings, period_rates, standing)
    assert "total_cost_gbp" in result
    assert "unit_cost_gbp" in result
    assert "standing_cost_gbp" in result
    assert "days_in_sample" in result

def test_current_annual_cost_scales_to_annual():
    readings = _readings(kwh_day=1.0, kwh_night=1.0, days=30)
    period_rates, standing = {p: 10.0 for p in range(48)}, 0.0
    result = current_annual_cost(readings, period_rates, standing)
    # 30 days × 48 periods × 1.0 kWh × 10p × (365/30) / 100 = £1752
    assert result["total_cost_gbp"] == pytest.approx(1752.0, rel=0.01)


# --- rank_alternatives ---

def test_rank_alternatives_drive_wins_heavy_night():
    readings = _readings(kwh_night=1.0, kwh_day=0.1)   # mostly night → Drive cheaper
    period_rates, standing = _actual_rates()
    current_gbp = current_annual_cost(readings, period_rates, standing)["total_cost_gbp"]
    ranked = rank_alternatives(readings, current_gbp, _eon_products())
    assert ranked[0]["product"] == "E.ON Next Drive"

def test_rank_alternatives_saving_fields_present():
    readings = _readings()
    period_rates, standing = _actual_rates()
    current_gbp = current_annual_cost(readings, period_rates, standing)["total_cost_gbp"]
    ranked = rank_alternatives(readings, current_gbp, _eon_products())
    for r in ranked:
        assert "saving_vs_current_gbp" in r
        assert "annual_cost_gbp" in r

def test_rank_alternatives_excludes_actual_products():
    readings = _readings()
    period_rates, standing = _actual_rates()
    current_gbp = current_annual_cost(readings, period_rates, standing)["total_cost_gbp"]
    products = _eon_products() + [
        {"name": "E.ON Next Flex", "product_type": "actual", "standing_p_day": None, "bands": []}
    ]
    ranked = rank_alternatives(readings, current_gbp, products)
    assert all(r["product_type"] != "actual" for r in ranked)

def test_rank_alternatives_sorted_best_saving_first():
    readings = _readings()
    period_rates, standing = _actual_rates()
    current_gbp = current_annual_cost(readings, period_rates, standing)["total_cost_gbp"]
    ranked = rank_alternatives(readings, current_gbp, _eon_products())
    savings = [r["saving_vs_current_gbp"] for r in ranked]
    assert savings == sorted(savings, reverse=True)


# --- flag_too_close ---

def test_flag_too_close_marks_within_threshold():
    ranked = [
        {"product": "A", "saving_vs_current_gbp": 10.0},
        {"product": "B", "saving_vs_current_gbp": -5.0},
    ]
    result = flag_too_close(ranked, threshold_gbp=20.0)
    assert result[0]["too_close"] is True

def test_flag_too_close_clears_large_gap():
    ranked = [
        {"product": "A", "saving_vs_current_gbp": 100.0},
        {"product": "B", "saving_vs_current_gbp": -100.0},
    ]
    result = flag_too_close(ranked, threshold_gbp=20.0)
    assert result[0]["too_close"] is False

def test_flag_too_close_false_when_no_saving():
    # Best saving is negative — no alternative saves money, should not be too_close
    ranked = [
        {"product": "A", "saving_vs_current_gbp": -50.0},
        {"product": "B", "saving_vs_current_gbp": -200.0},
    ]
    result = flag_too_close(ranked, threshold_gbp=20.0)
    assert result[0]["too_close"] is False

import pytest
from s01_tariff_matching import rank_tariffs, flag_too_close


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


def test_rank_tariffs_cheapest_first():
    readings = _readings(kwh_night=1.0, kwh_day=0.1)   # mostly night → Drive should win
    period_rates, standing = _actual_rates()
    ranked = rank_tariffs(readings, period_rates, standing, _eon_products())
    assert ranked[0]["product"] == "E.ON Next Drive"

def test_rank_tariffs_saving_computed():
    readings = _readings(kwh_night=0.0, kwh_day=1.0)   # all day usage → Fixed cheapest
    period_rates, standing = _actual_rates()
    ranked = rank_tariffs(readings, period_rates, standing, _eon_products())
    for r in ranked:
        assert "saving_vs_current_gbp" in r
        assert "annual_cost_gbp" in r

def test_rank_tariffs_flex_uses_actual_rates():
    readings = _readings()
    period_rates, standing = _actual_rates()
    products = [{"name": "E.ON Next Flex", "product_type": "actual",
                 "standing_p_day": None, "bands": []}]
    ranked = rank_tariffs(readings, period_rates, standing, products)
    # Flex uses actual rates → saving_vs_current = 0
    assert ranked[0]["saving_vs_current_gbp"] == pytest.approx(0.0, abs=0.01)


# --- flag_too_close ---

def test_flag_too_close_marks_within_threshold():
    ranked = [
        {"product": "A", "annual_cost_gbp": 1000.0, "saving_vs_current_gbp": 10.0},
        {"product": "B", "annual_cost_gbp": 1015.0, "saving_vs_current_gbp": -5.0},
    ]
    result = flag_too_close(ranked, threshold_gbp=20.0)
    assert result[0]["too_close"] is True

def test_flag_too_close_clears_large_gap():
    ranked = [
        {"product": "A", "annual_cost_gbp": 1000.0, "saving_vs_current_gbp": 100.0},
        {"product": "B", "annual_cost_gbp": 1200.0, "saving_vs_current_gbp": -100.0},
    ]
    result = flag_too_close(ranked, threshold_gbp=20.0)
    assert result[0]["too_close"] is False

import pytest
from datetime import date, timedelta
from occupancy_model import OccupancySchedule, DEFAULT_SCHEDULE, generate_occupancy


def test_occupancy_schedule_stores_fields():
    s = OccupancySchedule(weekday=["home"] * 48, weekend=["away"] * 48)
    assert s.weekday[0] == "home"
    assert s.weekend[0] == "away"


def test_default_schedule_weekday_length():
    assert len(DEFAULT_SCHEDULE.weekday) == 48
    assert len(DEFAULT_SCHEDULE.weekend) == 48


def test_default_schedule_weekday_away_period():
    # 08:30 = slot 17; 17:00 = slot 34
    assert DEFAULT_SCHEDULE.weekday[17] == "away"
    assert DEFAULT_SCHEDULE.weekday[34] == "away"


def test_default_schedule_weekday_evening_home():
    # 17:30 = slot 35
    assert DEFAULT_SCHEDULE.weekday[35] == "home"


def test_default_schedule_weekend_all_home_or_sleep():
    assert all(s in ("home", "sleep") for s in DEFAULT_SCHEDULE.weekend)


def test_generate_occupancy_weekday_away_slots_false():
    monday = date(2020, 1, 6)  # weekday() == 0
    occ = generate_occupancy(DEFAULT_SCHEDULE, [monday])
    assert occ[monday][17] is False  # 08:30 away
    assert occ[monday][34] is False  # 17:00 away


def test_generate_occupancy_weekday_home_and_sleep_true():
    monday = date(2020, 1, 6)
    occ = generate_occupancy(DEFAULT_SCHEDULE, [monday])
    assert occ[monday][0] is True    # 00:00 sleep
    assert occ[monday][35] is True   # 17:30 home


def test_generate_occupancy_weekend_all_true():
    saturday = date(2020, 1, 4)  # weekday() == 5
    occ = generate_occupancy(DEFAULT_SCHEDULE, [saturday])
    assert all(occ[saturday])


def test_generate_occupancy_returns_48_bools_per_date():
    dates = [date(2020, 1, 6), date(2020, 1, 7)]
    occ = generate_occupancy(DEFAULT_SCHEDULE, dates)
    for d in dates:
        assert len(occ[d]) == 48
        assert all(isinstance(v, bool) for v in occ[d])


def test_generate_occupancy_reproducible():
    dates = [date(2020, 1, 6)]
    assert (generate_occupancy(DEFAULT_SCHEDULE, dates, seed=42) ==
            generate_occupancy(DEFAULT_SCHEDULE, dates, seed=42))


def test_generate_occupancy_weekday_home_fraction_within_2pp():
    """Home fraction in generated signal must match schedule within ±2pp."""
    schedule_home_count = sum(
        1 for s in DEFAULT_SCHEDULE.weekday if s in ("home", "sleep")
    )
    schedule_fraction = schedule_home_count / 48

    weekdays = [date(2020, 1, 6) + timedelta(days=i) for i in range(5)]
    occ = generate_occupancy(DEFAULT_SCHEDULE, weekdays)
    for d in weekdays:
        actual = sum(occ[d]) / 48
        assert abs(actual - schedule_fraction) <= 0.02

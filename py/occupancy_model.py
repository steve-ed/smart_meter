from dataclasses import dataclass
from datetime import date


@dataclass
class OccupancySchedule:
    weekday: list[str]  # length 48; each element 'home', 'away', or 'sleep'
    weekend: list[str]  # length 48


def _default_weekday() -> list[str]:
    schedule = []
    for slot in range(48):
        if slot < 14:     # 00:00–06:30  sleep
            schedule.append("sleep")
        elif slot < 17:   # 07:00–08:30  home (getting ready)
            schedule.append("home")
        elif slot < 35:   # 08:30–17:00  away
            schedule.append("away")
        elif slot < 46:   # 17:30–22:30  home
            schedule.append("home")
        else:             # 23:00–23:30  sleep
            schedule.append("sleep")
    return schedule


def _default_weekend() -> list[str]:
    schedule = []
    for slot in range(48):
        if slot < 16:     # 00:00–07:30  sleep
            schedule.append("sleep")
        elif slot < 46:   # 08:00–22:30  home
            schedule.append("home")
        else:             # 23:00–23:30  sleep
            schedule.append("sleep")
    return schedule


DEFAULT_SCHEDULE = OccupancySchedule(
    weekday=_default_weekday(),
    weekend=_default_weekend(),
)


def generate_occupancy(
    schedule: OccupancySchedule,
    dates: list[date],
    seed: int = 42,
) -> dict[date, list[bool]]:
    """
    Generate deterministic binary (home/away) half-hourly occupancy signal.

    'home' and 'sleep' both map to True (occupant present in dwelling);
    'away' maps to False. Weekend = weekday() >= 5.

    Returns dict[date, list[48 bool]].

    The seed parameter is accepted for interface consistency with appliance_model
    but has no effect; the occupancy signal is fully deterministic from the schedule.
    """
    result: dict[date, list[bool]] = {}
    for d in dates:
        template = schedule.weekend if d.weekday() >= 5 else schedule.weekday
        result[d] = [s in ("home", "sleep") for s in template]
    return result

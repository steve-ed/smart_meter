import hashlib
import math
import random
from dataclasses import dataclass
from datetime import date

_SUMMER_MONTHS: frozenset[int] = frozenset({6, 7, 8})  # meteorological summer; home_model uses broader May–Sep thermal season


@dataclass
class ApplianceParams:
    rated_power_w: float          # watts at rated load
    event_duration_min: float     # minutes per event
    daily_frequency: float        # events per day (per occupant if scales_with_occupants)
    seasonal_factor: float = 1.0  # multiplier on daily_frequency for summer (Jun–Aug)
    occupancy_correlated: bool = True    # events only during home/sleep slots
    scales_with_occupants: bool = False  # multiply daily_frequency by occupant_count
    awake_only: bool = False             # if True, restrict further to 'home' slots (exclude 'sleep')


DEFAULT_APPLIANCES: dict[str, ApplianceParams] = {
    "water_heater": ApplianceParams(
        rated_power_w=2500.0,
        event_duration_min=30.0,
        daily_frequency=3.0,
        awake_only=False,   # hot water fires overnight (Economy 7 pattern)
    ),
    "fridge": ApplianceParams(
        rated_power_w=150.0,
        event_duration_min=15.0,
        daily_frequency=48.0,
        seasonal_factor=1.1,
        occupancy_correlated=False,
    ),
    "cooker": ApplianceParams(
        rated_power_w=2500.0,
        event_duration_min=45.0,
        daily_frequency=1.5,
        awake_only=True,
    ),
    "kettle": ApplianceParams(
        rated_power_w=2500.0,
        event_duration_min=3.0,
        daily_frequency=6.0,
        awake_only=True,
    ),
    "washing_machine": ApplianceParams(
        rated_power_w=2000.0,
        event_duration_min=75.0,
        daily_frequency=0.7,
        awake_only=True,
    ),
    "dryer": ApplianceParams(
        rated_power_w=3000.0,
        event_duration_min=52.0,
        daily_frequency=0.4,
        awake_only=True,
    ),
    "shower": ApplianceParams(
        rated_power_w=9000.0,
        event_duration_min=7.0,
        daily_frequency=1.0,
        scales_with_occupants=True,
        awake_only=True,
    ),
}


def generate_appliance_signal(
    appliance_id: str,
    params: ApplianceParams,
    dates: list[date],
    occupancy: dict[date, list[str]],
    seed: int = 42,
    occupant_count: int = 2,
) -> dict[date, list[float]]:
    """
    Generate half-hourly energy (kWh) for one appliance over the given dates.

    Events are placed using a seeded RNG for reproducibility. If
    params.occupancy_correlated is True, events are restricted to slots
    where the occupant is home. For high-frequency appliances (n_events >=
    len(available)), energy is distributed evenly across available slots
    rather than placed as discrete events.

    Returns dict[date, list[48 float]] -- kWh per half-hour.
    """
    rng = random.Random(seed)
    result: dict[date, list[float]] = {}
    event_slots = max(1, math.ceil(params.event_duration_min / 30.0))
    energy_per_event = params.rated_power_w / 1000.0 * params.event_duration_min / 60.0
    energy_per_slot = energy_per_event / event_slots

    for d in dates:
        slots = [0.0] * 48
        factor = params.seasonal_factor if d.month in _SUMMER_MONTHS else 1.0
        freq = params.daily_frequency * factor
        if params.scales_with_occupants:
            freq *= occupant_count

        occ = occupancy.get(d, ["home"] * 48)
        if not params.occupancy_correlated:
            available = list(range(48))
        elif params.awake_only:
            available = [i for i in range(48) if occ[i] == "home"]
        else:
            available = [i for i in range(48) if occ[i] in ("home", "sleep")]

        if not available:
            result[d] = slots
            continue

        n_whole = int(freq)
        n_events = n_whole + (1 if rng.random() < (freq - n_whole) else 0)

        if not params.occupancy_correlated and n_events >= len(available):
            # High-frequency appliance (e.g. fridge): distribute total energy evenly.
            total_energy = energy_per_event * freq
            per_slot = total_energy / len(available)
            for i in available:
                slots[i] += per_slot
        else:
            max_start = 48 - event_slots
            for _ in range(n_events):
                valid = [s for s in available if s <= max_start]
                if not valid:
                    continue  # no non-truncating start available; skip this event
                start = rng.choice(valid)
                for k in range(event_slots):
                    slots[start + k] += energy_per_slot

        result[d] = slots

    return result


def generate_electricity_profile(
    appliances: dict[str, ApplianceParams],
    dates: list[date],
    occupancy: dict[date, list[str]],
    seed: int = 42,
    occupant_count: int = 2,
) -> dict[date, list[float]]:
    """
    Generate half-hourly total electricity (kWh) as the superposition of all appliances.

    Each appliance receives a unique derived seed so their events are placed
    independently while remaining fully reproducible.

    Returns dict[date, list[48 float]] -- kWh per half-hour.
    """
    result: dict[date, list[float]] = {d: [0.0] * 48 for d in dates}
    for appliance_id, params in appliances.items():
        raw = hashlib.md5(f"{seed}:{appliance_id}".encode()).digest()
        appliance_seed = int.from_bytes(raw[:4], "little") & 0x7FFF_FFFF
        signal = generate_appliance_signal(
            appliance_id, params, dates, occupancy,
            seed=appliance_seed, occupant_count=occupant_count,
        )
        for d in dates:
            for i in range(48):
                result[d][i] += signal[d][i]
    return result

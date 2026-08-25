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


DEFAULT_APPLIANCES: dict[str, ApplianceParams] = {
    "water_heater": ApplianceParams(
        rated_power_w=2500.0,
        event_duration_min=30.0,
        daily_frequency=3.0,
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
    ),
    "kettle": ApplianceParams(
        rated_power_w=2500.0,
        event_duration_min=3.0,
        daily_frequency=6.0,
    ),
    "washing_machine": ApplianceParams(
        rated_power_w=2000.0,
        event_duration_min=75.0,
        daily_frequency=0.7,
    ),
    "dryer": ApplianceParams(
        rated_power_w=3000.0,
        event_duration_min=52.0,
        daily_frequency=0.4,
    ),
    "shower": ApplianceParams(
        rated_power_w=9000.0,
        event_duration_min=7.0,
        daily_frequency=1.0,
        scales_with_occupants=True,
    ),
}


def generate_appliance_signal(
    appliance_id: str,
    params: ApplianceParams,
    dates: list[date],
    occupancy: dict[date, list[bool]],
    seed: int = 42,
    occupant_count: int = 2,
) -> dict[date, list[float]]:
    raise NotImplementedError


def generate_electricity_profile(
    appliances: dict[str, ApplianceParams],
    dates: list[date],
    occupancy: dict[date, list[bool]],
    seed: int = 42,
    occupant_count: int = 2,
) -> dict[date, list[float]]:
    raise NotImplementedError

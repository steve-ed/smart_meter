"""
Top-level simulation runner.

Wires occupancy, appliance, solar, and forward thermal simulation into
a single run_simulation() call returning a SimulationResult.
"""
import csv
from dataclasses import dataclass
from datetime import date

from energy_model import DwellingParams, derived_quantities
from home_model import decay_step
from occupancy_model import DEFAULT_SCHEDULE, OccupancySchedule, generate_occupancy
from appliance_model import DEFAULT_APPLIANCES, ApplianceParams, generate_electricity_profile
from solar_model import generate_solar_profile


@dataclass
class WeatherSeries:
    outdoor_temp_c: dict[str, float]
    wind_speed_ms: dict[str, float]


@dataclass
class SimulationResult:
    dwelling: DwellingParams
    dates: list[date]
    timestamps: list[str]
    outdoor_temp_c: dict[str, float]
    wind_speed_ms: dict[str, float]
    occupancy: dict[str, bool]
    electricity_kwh: dict[str, float]
    gas_kwh: dict[str, float]
    indoor_temp_c: dict[str, float]
    boiler_on: dict[str, bool]
    solar_kwh: dict[str, float] | None


def _ts(d: date, slot: int) -> str:
    h, m = divmod(slot, 2)
    return f"{d} {h:02d}:{m * 30:02d}"


def _flatten_bool(series: dict[date, list[bool]], dates: list[date]) -> dict[str, bool]:
    out: dict[str, bool] = {}
    for d in dates:
        for slot, val in enumerate(series[d]):
            out[_ts(d, slot)] = val
    return out


def _flatten_float(series: dict[date, list[float]], dates: list[date]) -> dict[str, float]:
    out: dict[str, float] = {}
    for d in dates:
        for slot, val in enumerate(series[d]):
            out[_ts(d, slot)] = val
    return out


def load_weather(dates: list[date], weather_path: str = "data/weather.csv") -> WeatherSeries:
    """
    Read temp_c and wind_speed_ms from a weather CSV for the given dates.

    weather_path is relative to the process working directory (typically py/).
    Rows whose date is not in dates are skipped. Rows with unparseable float
    values are skipped; missing columns raise KeyError immediately.
    """
    date_strs = {str(d) for d in dates}
    temp_c: dict[str, float] = {}
    wind_ms: dict[str, float] = {}
    with open(weather_path, newline="") as f:
        for row in csv.DictReader(f):
            ts = row["timestamp"]
            if ts[:10] not in date_strs:
                continue
            try:
                temp_c[ts] = float(row["temp_c"])
                wind_ms[ts] = float(row["wind_speed_ms"])
            except ValueError:
                pass
    return WeatherSeries(outdoor_temp_c=temp_c, wind_speed_ms=wind_ms)

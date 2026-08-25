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


_HEATING_MONTHS: frozenset[int] = frozenset({10, 11, 12, 1, 2, 3, 4})


def forward_simulate(
    dp: DwellingParams,
    dates: list[date],
    weather: WeatherSeries,
) -> tuple[dict[str, float], dict[str, float], dict[str, bool]]:
    """
    Generate synthetic indoor_temp_c, gas_kwh, boiler_on from dwelling physics.

    Space heating fires when the decayed indoor temperature would fall below
    dp.t_setpoint during heating months (Oct–Apr).  Gas per slot is
    space-heating gas + dp.base_load_kwh_per_period.
    """
    dq = derived_quantities(dp)
    tau = dq["tau_hours"]
    c_wh_per_k = dq["c_wh_per_k"]

    indoor_temp: dict[str, float] = {}
    gas_out: dict[str, float] = {}
    boiler_out: dict[str, bool] = {}

    t_indoor = dp.t_setpoint

    for d in dates:
        in_heating = d.month in _HEATING_MONTHS
        for slot in range(48):
            ts = _ts(d, slot)
            t_out = weather.outdoor_temp_c.get(ts, t_indoor)

            t_decay = decay_step(t_indoor, t_out, tau)

            if in_heating and t_decay < dp.t_setpoint:
                heat_needed_wh = (dp.t_setpoint - t_decay) * c_wh_per_k
                gas_heat_kwh = heat_needed_wh / (dp.heating_efficiency * 1000.0)
                t_indoor = dp.t_setpoint
                boiler_on = True
            else:
                t_indoor = max(t_decay, t_out)
                gas_heat_kwh = 0.0
                boiler_on = False

            indoor_temp[ts] = round(t_indoor, 3)
            gas_out[ts] = gas_heat_kwh + dp.base_load_kwh_per_period
            boiler_out[ts] = boiler_on

    return indoor_temp, gas_out, boiler_out

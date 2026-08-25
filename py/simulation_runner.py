"""
Top-level simulation runner.

Wires occupancy, appliance, solar, and forward thermal simulation into
a single run_simulation() call returning a SimulationResult.
"""
import csv
import warnings
from dataclasses import dataclass
from datetime import date

from energy_model import DwellingParams, derived_quantities
from home_model import decay_step
from occupancy_model import DEFAULT_SCHEDULE, OccupancySchedule, generate_occupancy, generate_occupancy_states
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
                warnings.warn(f"load_weather: skipping row with unparseable values at {ts}")
    return WeatherSeries(outdoor_temp_c=temp_c, wind_speed_ms=wind_ms)


# Oct–Apr. May is a shoulder month with no space heating; Jun–Sep are summer.
_HEATING_MONTHS: frozenset[int] = frozenset({10, 11, 12, 1, 2, 3, 4})

# Typical UK programmer: comfort temperature during waking/home periods, setback elsewhere.
# Mirrors the DEFAULT_SCHEDULE occupancy pattern (sleep→setback, away→setback, home→comfort).
def _default_setpoint_schedule() -> list[float]:
    schedule = []
    for slot in range(48):
        if slot < 14:     # 00:00–06:30  sleep setback
            schedule.append(16.0)
        elif slot < 17:   # 07:00–08:00  morning warmup
            schedule.append(20.0)
        elif slot < 35:   # 08:30–17:00  away setback
            schedule.append(16.0)
        elif slot < 46:   # 17:30–22:30  evening comfort
            schedule.append(20.0)
        else:             # 23:00–23:30  sleep setback
            schedule.append(16.0)
    return schedule


DEFAULT_SETPOINT_SCHEDULE: list[float] = _default_setpoint_schedule()


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

    If a timestamp is absent from weather.outdoor_temp_c, outdoor temperature
    defaults to the current indoor temperature (zero heat loss for that slot).
    """
    dq = derived_quantities(dp)
    if dq["htc"] <= 0.0:
        raise ValueError(
            "DwellingParams has zero or negative HTC — check that U-values and q50 are set. "
            "Use create_dwelling() or set all fabric parameters."
        )
    tau = dq["tau_hours"]
    c_wh_per_k = dq["c_wh_per_k"]

    setpoint_sched = dp.t_setpoint_schedule
    if setpoint_sched is not None and len(setpoint_sched) != 48:
        raise ValueError(
            f"t_setpoint_schedule must have 48 values (one per half-hour slot), "
            f"got {len(setpoint_sched)}"
        )

    indoor_temp: dict[str, float] = {}
    gas_out: dict[str, float] = {}
    boiler_out: dict[str, bool] = {}

    t_indoor = dp.t_setpoint

    for d in dates:
        in_heating = d.month in _HEATING_MONTHS
        for slot in range(48):
            ts = _ts(d, slot)
            t_out = weather.outdoor_temp_c.get(ts, t_indoor)
            setpoint = setpoint_sched[slot] if setpoint_sched is not None else dp.t_setpoint

            t_decay = decay_step(t_indoor, t_out, tau)

            if in_heating and t_decay < setpoint:
                heat_needed_wh = (setpoint - t_decay) * c_wh_per_k
                gas_heat_kwh = heat_needed_wh / (dp.heating_efficiency * 1000.0)
                if dp.boiler_max_kw > 0.0:
                    gas_heat_kwh = min(gas_heat_kwh, dp.boiler_max_kw * 0.5)
                heat_delivered_wh = gas_heat_kwh * dp.heating_efficiency * 1000.0
                t_indoor = min(t_decay + heat_delivered_wh / c_wh_per_k, setpoint)
                boiler_on = True
            else:
                t_indoor = max(t_decay, t_out)
                gas_heat_kwh = 0.0
                boiler_on = False

            indoor_temp[ts] = round(t_indoor, 3)
            gas_out[ts] = gas_heat_kwh + dp.base_load_kwh_per_period
            boiler_out[ts] = boiler_on

    return indoor_temp, gas_out, boiler_out


def run_simulation(
    dp: DwellingParams,
    dates: list[date],
    schedule: OccupancySchedule = DEFAULT_SCHEDULE,
    appliances: dict[str, ApplianceParams] = DEFAULT_APPLIANCES,
    seed: int = 42,
    lat: float = 53.6,
    lon: float = -1.32,
    pvgis_year: int = 2020,
    weather_path: str = "data/weather.csv",
    pvgis_cache_dir: str = "data",
) -> SimulationResult:
    """
    Run a full synthetic simulation for a dwelling over the given dates.

    Returns a SimulationResult with all series keyed by 'YYYY-MM-DD HH:MM'
    timestamp strings, one per half-hour slot.
    """
    weather = load_weather(dates, weather_path)
    occupancy_states = generate_occupancy_states(schedule, dates, seed=seed)
    occupancy_bool = {d: [s in ("home", "sleep") for s in slots]
                      for d, slots in occupancy_states.items()}
    elec_by_date = generate_electricity_profile(
        appliances, dates, occupancy_states,
        seed=seed, occupant_count=dp.occupant_count,
    )
    indoor_temp, gas, boiler_on = forward_simulate(dp, dates, weather)
    solar_by_date = generate_solar_profile(
        dp, lat=lat, lon=lon, year=pvgis_year, cache_dir=pvgis_cache_dir,
    )

    timestamps = [_ts(d, s) for d in dates for s in range(48)]
    solar_flat = _flatten_float(solar_by_date, dates) if solar_by_date is not None else None

    return SimulationResult(
        dwelling=dp,
        dates=dates,
        timestamps=timestamps,
        outdoor_temp_c=weather.outdoor_temp_c,
        wind_speed_ms=weather.wind_speed_ms,
        occupancy=_flatten_bool(occupancy_bool, dates),
        electricity_kwh=_flatten_float(elec_by_date, dates),
        gas_kwh=gas,
        indoor_temp_c=indoor_temp,
        boiler_on=boiler_on,
        solar_kwh=solar_flat,
    )

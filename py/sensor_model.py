"""
Sensor noise model for smart meter ground truth data.

Reads a ground truth CSV (produced by gen_ground_truth_m6.py) and applies
per-channel noise to produce synthetic sensor observations.

Noise models
------------
outdoor_temp_c  Gaussian additive + systematic bias  (weather station)
wind_speed_ms   Gaussian additive, clipped to ≥ 0    (cup anemometer)
indoor_temp_c   Gaussian additive + systematic bias  (room sensor)
electricity_kwh Multiplicative proportional Gaussian  (SMETS2 meter, ±0.5 %)
gas_kwh         Multiplicative proportional Gaussian  (SMETS2 meter, ±1 %)
occupancy       Binary flip: false-positive / false-negative rates (PIR)
boiler_on       Relay / digital signal — modelled as perfect (no noise)

Usage
-----
    from sensor_model import SensorNoiseModel, load_ground_truth, apply_noise, write_observations

    rows  = load_ground_truth("data/ground_truth_m6_2024.csv")
    noisy = apply_noise(rows, SensorNoiseModel(), seed=42)
    write_observations(noisy, "data/observations_m6_2024.csv")
"""
import csv
import random
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Per-channel noise parameter dataclasses
# ---------------------------------------------------------------------------

@dataclass
class TemperatureNoise:
    sigma_c: float = 0.2   # Gaussian std dev (°C)
    bias_c:  float = 0.0   # systematic offset (°C)


@dataclass
class EnergyNoise:
    """Multiplicative proportional noise: observed = true × N(1, sigma_fraction)."""
    sigma_fraction: float = 0.005  # fractional std dev (dimensionless)


@dataclass
class OccupancyNoise:
    false_positive_rate: float = 0.02  # P(sensor says occupied | truly vacant)
    false_negative_rate: float = 0.05  # P(sensor says vacant   | truly occupied)


@dataclass
class WindNoise:
    sigma_ms: float = 0.5  # Gaussian std dev (m/s); output clipped to ≥ 0


# ---------------------------------------------------------------------------
# Composite noise model
# ---------------------------------------------------------------------------

@dataclass
class SensorNoiseModel:
    outdoor_temp: TemperatureNoise = field(
        default_factory=lambda: TemperatureNoise(sigma_c=0.3, bias_c=0.0)
    )
    indoor_temp: TemperatureNoise = field(
        default_factory=lambda: TemperatureNoise(sigma_c=0.2, bias_c=0.0)
    )
    electricity: EnergyNoise = field(
        default_factory=lambda: EnergyNoise(sigma_fraction=0.005)
    )
    gas: EnergyNoise = field(
        default_factory=lambda: EnergyNoise(sigma_fraction=0.010)
    )
    occupancy: OccupancyNoise = field(default_factory=OccupancyNoise)
    wind: WindNoise = field(default_factory=WindNoise)


DEFAULT_NOISE = SensorNoiseModel()


# ---------------------------------------------------------------------------
# Noise application helpers
# ---------------------------------------------------------------------------

def _add_temp_noise(value: float, params: TemperatureNoise, rng: random.Random) -> float:
    return round(value + params.bias_c + rng.gauss(0.0, params.sigma_c), 3)


def _add_energy_noise(value: float, params: EnergyNoise, rng: random.Random) -> float:
    """Proportional noise; negative observations are clamped to 0."""
    observed = value * (1.0 + rng.gauss(0.0, params.sigma_fraction))
    return round(max(observed, 0.0), 6)


def _add_wind_noise(value: float, params: WindNoise, rng: random.Random) -> float:
    observed = value + rng.gauss(0.0, params.sigma_ms)
    return round(max(observed, 0.0), 2)


def _flip_occupancy(value: bool, params: OccupancyNoise, rng: random.Random) -> bool:
    if value:
        return rng.random() >= params.false_negative_rate
    else:
        return rng.random() < params.false_positive_rate


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

GROUND_TRUTH_FIELDS = [
    "timestamp", "outdoor_temp_c", "wind_speed_ms", "occupancy",
    "electricity_kwh", "gas_kwh", "indoor_temp_c", "boiler_on",
]


def load_ground_truth(path: str) -> list[dict]:
    """Read a ground truth CSV and return rows as a list of dicts (typed values)."""
    rows = []
    with open(path, newline="") as f:
        for raw in csv.DictReader(f):
            rows.append({
                "timestamp":       raw["timestamp"],
                "outdoor_temp_c":  float(raw["outdoor_temp_c"]),
                "wind_speed_ms":   float(raw["wind_speed_ms"]),
                "occupancy":       bool(int(raw["occupancy"])),
                "electricity_kwh": float(raw["electricity_kwh"]),
                "gas_kwh":         float(raw["gas_kwh"]),
                "indoor_temp_c":   float(raw["indoor_temp_c"]),
                "boiler_on":       bool(int(raw["boiler_on"])),
            })
    return rows


def apply_noise(
    rows: list[dict],
    model: SensorNoiseModel = DEFAULT_NOISE,
    seed: int = 42,
) -> list[dict]:
    """
    Apply per-channel sensor noise to ground truth rows.

    Returns a new list of dicts with the same keys. boiler_on is passed
    through unchanged (relay/digital signal — modelled as perfect).
    NaN outdoor_temp_c / wind_speed_ms values (missing weather) are left as NaN.
    """
    rng = random.Random(seed)
    out = []
    for row in rows:
        ot = row["outdoor_temp_c"]
        ws = row["wind_speed_ms"]
        out.append({
            "timestamp":       row["timestamp"],
            "outdoor_temp_c":  (
                _add_temp_noise(ot, model.outdoor_temp, rng)
                if ot == ot else float("nan")   # NaN check
            ),
            "wind_speed_ms":   (
                _add_wind_noise(ws, model.wind, rng)
                if ws == ws else float("nan")
            ),
            "occupancy":       _flip_occupancy(row["occupancy"], model.occupancy, rng),
            "electricity_kwh": _add_energy_noise(row["electricity_kwh"], model.electricity, rng),
            "gas_kwh":         _add_energy_noise(row["gas_kwh"], model.gas, rng),
            "indoor_temp_c":   _add_temp_noise(row["indoor_temp_c"], model.indoor_temp, rng),
            "boiler_on":       row["boiler_on"],
        })
    return out


def write_observations(rows: list[dict], path: str) -> None:
    """Write noisy observations to CSV in the same column order as ground truth."""
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=GROUND_TRUTH_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "timestamp":       row["timestamp"],
                "outdoor_temp_c":  row["outdoor_temp_c"],
                "wind_speed_ms":   row["wind_speed_ms"],
                "occupancy":       int(row["occupancy"]),
                "electricity_kwh": row["electricity_kwh"],
                "gas_kwh":         row["gas_kwh"],
                "indoor_temp_c":   row["indoor_temp_c"],
                "boiler_on":       int(row["boiler_on"]),
            })

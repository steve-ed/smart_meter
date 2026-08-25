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
        noisy = {
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
        }
        if "indoor_temp_c_z2" in row:
            noisy["indoor_temp_c_z2"] = _add_temp_noise(
                row["indoor_temp_c_z2"], model.indoor_temp, rng
            )
        out.append(noisy)
    return out


def kalman_smooth_series(
    observations: list[float],
    process_sigma: float,
    measurement_sigma: float,
) -> list[float]:
    """
    RTS Kalman smoother for a 1D time series (random-walk state model).

    process_sigma     : expected std dev of true value change per time step
    measurement_sigma : sensor noise std dev (matches noise applied earlier)

    NaN observations skip the update step — the filter coasts on the prediction.
    Returns a list of smoothed values the same length as observations.
    """
    n = len(observations)
    if n == 0:
        return []

    Q = process_sigma ** 2
    R = measurement_sigma ** 2

    x_f = [0.0] * n   # filtered mean
    P_f = [0.0] * n   # filtered variance
    x_p = [0.0] * n   # predicted mean
    P_p = [0.0] * n   # predicted variance

    # Forward pass — initialise from first valid observation
    first = next((v for v in observations if v == v), 0.0)
    x_f[0] = first
    P_f[0] = R

    for k in range(1, n):
        x_p[k] = x_f[k - 1]
        P_p[k] = P_f[k - 1] + Q
        z = observations[k]
        if z != z:          # NaN: skip update, coast on prediction
            x_f[k] = x_p[k]
            P_f[k] = P_p[k]
        else:
            K       = P_p[k] / (P_p[k] + R)
            x_f[k]  = x_p[k] + K * (z - x_p[k])
            P_f[k]  = (1.0 - K) * P_p[k]

    # Backward RTS smoother pass
    x_s = list(x_f)
    P_s = list(P_f)

    for k in range(n - 2, -1, -1):
        G      = P_f[k] / P_p[k + 1]
        x_s[k] = x_f[k] + G * (x_s[k + 1] - x_p[k + 1])
        P_s[k] = P_f[k] + G * (P_s[k + 1] - P_p[k + 1]) * G

    return x_s


def smooth_observations(
    rows: list[dict],
    indoor_process_sigma: float = 0.05,
    outdoor_process_sigma: float = 0.30,
    indoor_measurement_sigma: float = 0.20,
    outdoor_measurement_sigma: float = 0.30,
) -> list[dict]:
    """
    Apply RTS Kalman smoother to indoor_temp_c and outdoor_temp_c observation
    columns. Returns new rows with 'indoor_temp_c_smooth' and
    'outdoor_temp_c_smooth' keys added.

    Default process_sigma values reflect physical constraints:
      indoor  0.05°C/slot — slow change, dominated by thermal mass
      outdoor 0.30°C/slot — weather changes faster but still smooth
    """
    indoor_smooth = kalman_smooth_series(
        [r["indoor_temp_c"] for r in rows],
        process_sigma=indoor_process_sigma,
        measurement_sigma=indoor_measurement_sigma,
    )
    outdoor_smooth = kalman_smooth_series(
        [r["outdoor_temp_c"] for r in rows],
        process_sigma=outdoor_process_sigma,
        measurement_sigma=outdoor_measurement_sigma,
    )
    result = [
        {
            **r,
            "indoor_temp_c_smooth":  round(si, 3),
            "outdoor_temp_c_smooth": round(so, 3),
        }
        for r, si, so in zip(rows, indoor_smooth, outdoor_smooth)
    ]
    if rows and "indoor_temp_c_z2" in rows[0]:
        z2_smooth = kalman_smooth_series(
            [r["indoor_temp_c_z2"] for r in rows],
            process_sigma=indoor_process_sigma,
            measurement_sigma=indoor_measurement_sigma,
        )
        result = [
            {**r, "indoor_temp_c_z2_smooth": round(sz, 3)}
            for r, sz in zip(result, z2_smooth)
        ]
    return result


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

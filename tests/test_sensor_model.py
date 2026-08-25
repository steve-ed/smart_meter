import math
import statistics
import tempfile
import os
import pytest
from sensor_model import (
    DEFAULT_NOISE,
    EnergyNoise,
    OccupancyNoise,
    SensorNoiseModel,
    TemperatureNoise,
    WindNoise,
    apply_noise,
    load_ground_truth,
    write_observations,
    _add_temp_noise,
    _add_energy_noise,
    _add_wind_noise,
    _flip_occupancy,
)
import random


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_row(**overrides) -> dict:
    base = {
        "timestamp":       "2024-01-01 00:00",
        "outdoor_temp_c":  5.0,
        "wind_speed_ms":   3.0,
        "occupancy":       True,
        "electricity_kwh": 0.25,
        "gas_kwh":         1.50,
        "indoor_temp_c":   19.0,
        "boiler_on":       True,
    }
    base.update(overrides)
    return base


def _many_rows(n: int = 1000, **overrides) -> list[dict]:
    return [_make_row(**overrides) for _ in range(n)]


# ---------------------------------------------------------------------------
# TemperatureNoise
# ---------------------------------------------------------------------------

class TestTemperatureNoise:
    def test_zero_noise_returns_value_plus_bias(self):
        p = TemperatureNoise(sigma_c=0.0, bias_c=1.5)
        rng = random.Random(0)
        assert _add_temp_noise(10.0, p, rng) == pytest.approx(11.5, abs=1e-6)

    def test_gaussian_noise_mean_near_true_value(self):
        p = TemperatureNoise(sigma_c=0.5, bias_c=0.0)
        rng = random.Random(42)
        samples = [_add_temp_noise(15.0, p, rng) for _ in range(2000)]
        assert abs(statistics.mean(samples) - 15.0) < 0.05

    def test_gaussian_noise_std_near_sigma(self):
        p = TemperatureNoise(sigma_c=0.5, bias_c=0.0)
        rng = random.Random(42)
        samples = [_add_temp_noise(15.0, p, rng) for _ in range(2000)]
        assert abs(statistics.stdev(samples) - 0.5) < 0.05

    def test_bias_shifts_mean(self):
        p = TemperatureNoise(sigma_c=0.1, bias_c=2.0)
        rng = random.Random(42)
        samples = [_add_temp_noise(10.0, p, rng) for _ in range(2000)]
        assert abs(statistics.mean(samples) - 12.0) < 0.1

    def test_output_rounded_to_3dp(self):
        p = TemperatureNoise(sigma_c=0.0, bias_c=0.0)
        rng = random.Random(0)
        result = _add_temp_noise(10.12345, p, rng)
        assert result == round(result, 3)


# ---------------------------------------------------------------------------
# EnergyNoise
# ---------------------------------------------------------------------------

class TestEnergyNoise:
    def test_zero_sigma_returns_exact_value(self):
        p = EnergyNoise(sigma_fraction=0.0)
        rng = random.Random(0)
        assert _add_energy_noise(1.5, p, rng) == pytest.approx(1.5, abs=1e-9)

    def test_mean_near_true_value(self):
        p = EnergyNoise(sigma_fraction=0.01)
        rng = random.Random(42)
        samples = [_add_energy_noise(1.0, p, rng) for _ in range(2000)]
        assert abs(statistics.mean(samples) - 1.0) < 0.01

    def test_negative_values_clamped_to_zero(self):
        # Force negative output: sigma so large the draw will be < -1
        p = EnergyNoise(sigma_fraction=100.0)
        rng = random.Random(42)
        samples = [_add_energy_noise(0.001, p, rng) for _ in range(100)]
        assert all(s >= 0.0 for s in samples)

    def test_output_rounded_to_6dp(self):
        p = EnergyNoise(sigma_fraction=0.0)
        rng = random.Random(0)
        result = _add_energy_noise(0.123456789, p, rng)
        assert result == round(result, 6)


# ---------------------------------------------------------------------------
# WindNoise
# ---------------------------------------------------------------------------

class TestWindNoise:
    def test_never_negative(self):
        p = WindNoise(sigma_ms=10.0)
        rng = random.Random(42)
        samples = [_add_wind_noise(0.1, p, rng) for _ in range(500)]
        assert all(s >= 0.0 for s in samples)

    def test_mean_near_true_value_when_low_noise(self):
        p = WindNoise(sigma_ms=0.1)
        rng = random.Random(42)
        samples = [_add_wind_noise(5.0, p, rng) for _ in range(2000)]
        assert abs(statistics.mean(samples) - 5.0) < 0.05

    def test_output_rounded_to_2dp(self):
        p = WindNoise(sigma_ms=0.0)
        rng = random.Random(0)
        result = _add_wind_noise(3.14159, p, rng)
        assert result == round(result, 2)


# ---------------------------------------------------------------------------
# OccupancyNoise
# ---------------------------------------------------------------------------

class TestOccupancyNoise:
    def test_zero_rates_preserves_true(self):
        p = OccupancyNoise(false_positive_rate=0.0, false_negative_rate=0.0)
        rng = random.Random(0)
        assert _flip_occupancy(True, p, rng) is True
        assert _flip_occupancy(False, p, rng) is False

    def test_false_negative_rate_applied_to_occupied(self):
        p = OccupancyNoise(false_positive_rate=0.0, false_negative_rate=0.5)
        rng = random.Random(42)
        samples = [_flip_occupancy(True, p, rng) for _ in range(2000)]
        fn_rate = samples.count(False) / len(samples)
        assert abs(fn_rate - 0.5) < 0.05

    def test_false_positive_rate_applied_to_vacant(self):
        p = OccupancyNoise(false_positive_rate=0.3, false_negative_rate=0.0)
        rng = random.Random(42)
        samples = [_flip_occupancy(False, p, rng) for _ in range(2000)]
        fp_rate = samples.count(True) / len(samples)
        assert abs(fp_rate - 0.3) < 0.05

    def test_rate_one_always_flips_occupied(self):
        p = OccupancyNoise(false_positive_rate=0.0, false_negative_rate=1.0)
        rng = random.Random(0)
        assert all(not _flip_occupancy(True, p, rng) for _ in range(20))

    def test_rate_zero_never_flips_vacant(self):
        p = OccupancyNoise(false_positive_rate=0.0, false_negative_rate=0.0)
        rng = random.Random(0)
        assert all(not _flip_occupancy(False, p, rng) for _ in range(20))


# ---------------------------------------------------------------------------
# apply_noise
# ---------------------------------------------------------------------------

class TestApplyNoise:
    def test_returns_same_length(self):
        rows = _many_rows(10)
        out = apply_noise(rows, DEFAULT_NOISE, seed=0)
        assert len(out) == 10

    def test_boiler_on_unchanged(self):
        rows = [_make_row(boiler_on=True), _make_row(boiler_on=False)]
        out = apply_noise(rows, DEFAULT_NOISE, seed=0)
        assert out[0]["boiler_on"] is True
        assert out[1]["boiler_on"] is False

    def test_timestamp_unchanged(self):
        rows = [_make_row(timestamp="2024-06-15 12:30")]
        out = apply_noise(rows, DEFAULT_NOISE, seed=0)
        assert out[0]["timestamp"] == "2024-06-15 12:30"

    def test_reproducible_with_same_seed(self):
        rows = _many_rows(50)
        assert apply_noise(rows, DEFAULT_NOISE, seed=7) == apply_noise(rows, DEFAULT_NOISE, seed=7)

    def test_different_seeds_give_different_results(self):
        rows = _many_rows(50)
        out_a = apply_noise(rows, DEFAULT_NOISE, seed=1)
        out_b = apply_noise(rows, DEFAULT_NOISE, seed=2)
        temps_a = [r["indoor_temp_c"] for r in out_a]
        temps_b = [r["indoor_temp_c"] for r in out_b]
        assert temps_a != temps_b

    def test_energy_noise_mean_close_to_truth(self):
        rows = _many_rows(2000, electricity_kwh=1.0)
        out = apply_noise(rows, DEFAULT_NOISE, seed=42)
        mean_obs = statistics.mean(r["electricity_kwh"] for r in out)
        assert abs(mean_obs - 1.0) < 0.02

    def test_wind_never_negative(self):
        rows = _many_rows(500, wind_speed_ms=0.1)
        out = apply_noise(rows, DEFAULT_NOISE, seed=42)
        assert all(r["wind_speed_ms"] >= 0.0 for r in out)

    def test_nan_outdoor_temp_preserved(self):
        rows = [_make_row(outdoor_temp_c=float("nan"))]
        out = apply_noise(rows, DEFAULT_NOISE, seed=0)
        assert math.isnan(out[0]["outdoor_temp_c"])

    def test_nan_wind_preserved(self):
        rows = [_make_row(wind_speed_ms=float("nan"))]
        out = apply_noise(rows, DEFAULT_NOISE, seed=0)
        assert math.isnan(out[0]["wind_speed_ms"])

    def test_zero_noise_model_leaves_temperatures_unchanged(self):
        model = SensorNoiseModel(
            outdoor_temp=TemperatureNoise(sigma_c=0.0, bias_c=0.0),
            indoor_temp=TemperatureNoise(sigma_c=0.0, bias_c=0.0),
            electricity=EnergyNoise(sigma_fraction=0.0),
            gas=EnergyNoise(sigma_fraction=0.0),
            occupancy=OccupancyNoise(false_positive_rate=0.0, false_negative_rate=0.0),
            wind=WindNoise(sigma_ms=0.0),
        )
        rows = [_make_row()]
        out = apply_noise(rows, model, seed=0)
        assert out[0]["outdoor_temp_c"] == pytest.approx(5.0)
        assert out[0]["indoor_temp_c"]  == pytest.approx(19.0)
        assert out[0]["electricity_kwh"] == pytest.approx(0.25)
        assert out[0]["gas_kwh"] == pytest.approx(1.50)
        assert out[0]["occupancy"] is True


# ---------------------------------------------------------------------------
# load_ground_truth / write_observations round-trip
# ---------------------------------------------------------------------------

class TestCSVRoundTrip:
    def _write_csv(self, path, rows):
        import csv as _csv
        fields = [
            "timestamp", "outdoor_temp_c", "wind_speed_ms", "occupancy",
            "electricity_kwh", "gas_kwh", "indoor_temp_c", "boiler_on",
        ]
        with open(path, "w", newline="") as f:
            w = _csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for row in rows:
                w.writerow({
                    **row,
                    "occupancy": int(row["occupancy"]),
                    "boiler_on": int(row["boiler_on"]),
                })

    def test_load_returns_correct_types(self, tmp_path):
        src = [_make_row()]
        p = str(tmp_path / "gt.csv")
        self._write_csv(p, src)
        loaded = load_ground_truth(p)
        assert isinstance(loaded[0]["outdoor_temp_c"], float)
        assert isinstance(loaded[0]["occupancy"], bool)
        assert isinstance(loaded[0]["boiler_on"], bool)
        assert isinstance(loaded[0]["timestamp"], str)

    def test_load_write_load_preserves_values(self, tmp_path):
        model = SensorNoiseModel(
            outdoor_temp=TemperatureNoise(sigma_c=0.0),
            indoor_temp=TemperatureNoise(sigma_c=0.0),
            electricity=EnergyNoise(sigma_fraction=0.0),
            gas=EnergyNoise(sigma_fraction=0.0),
            occupancy=OccupancyNoise(0.0, 0.0),
            wind=WindNoise(sigma_ms=0.0),
        )
        src = [_make_row()]
        src_path = str(tmp_path / "gt.csv")
        obs_path = str(tmp_path / "obs.csv")
        self._write_csv(src_path, src)

        rows = load_ground_truth(src_path)
        noisy = apply_noise(rows, model, seed=0)
        write_observations(noisy, obs_path)
        reloaded = load_ground_truth(obs_path)

        assert reloaded[0]["outdoor_temp_c"] == pytest.approx(5.0, abs=1e-3)
        assert reloaded[0]["electricity_kwh"] == pytest.approx(0.25, abs=1e-6)
        assert reloaded[0]["occupancy"] is True
        assert reloaded[0]["boiler_on"] is True

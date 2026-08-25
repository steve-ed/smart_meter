"""
Energy model — parameterised dwelling for value-added feature assessment.

Defines DwellingParams (full parameter catalogue), archetype presets,
derived quantities (HTC, τ), and sensor tier validation.

See docs/superpowers/specs/2026-08-25-energy-model-design.md for requirements.
"""

from dataclasses import dataclass


@dataclass
class DwellingParams:
    # ---- Geometry (required) ----
    total_floor_area_m2: float
    storey_height_m: float
    window_area_m2: float
    door_area_m2: float
    plan_aspect_ratio: float = 1.0

    # ---- Fabric ----
    u_wall: float = 0.0
    u_roof: float = 0.0
    u_floor: float = 0.0
    u_window: float = 0.0
    u_door: float = 0.0
    y_value: float = 0.09
    q50: float = 8.0
    kappa: float = 160.0

    # ---- Heating system ----
    heating_fuel: str = "gas"
    heating_system_type: str = "boiler"
    heating_efficiency: float = 0.89
    heat_threshold_kwh: float = 0.15
    t_setpoint: float = 20.0
    base_load_kwh_per_period: float = 0.08

    # ---- Solar (optional) ----
    solar_present: bool = False
    solar_peak_kw: float = 0.0
    solar_azimuth_deg: float = 180.0
    solar_tilt_deg: float = 35.0
    solar_performance_ratio: float = 0.8
    solar_export_metered: bool = False

    # ---- Battery (optional) ----
    battery_present: bool = False
    battery_capacity_kwh: float = 0.0
    battery_rte: float = 0.9
    battery_charge_rate_kw: float = 0.0
    battery_discharge_rate_kw: float = 0.0

    # ---- Sensors ----
    sensor_elec_meter: bool = True
    sensor_gas_meter: bool = True
    sensor_outdoor_temp: bool = False
    sensor_wind_speed: bool = False
    sensor_occupancy: bool = False
    sensor_indoor_temp: bool = False
    sensor_solar_generation: bool = False
    sensor_battery_state: bool = False

    # ---- Occupancy ----
    occupant_count: int = 2
    occupancy_source: str = "synthetic"

    # ---- Metadata ----
    label: str = ""
    archetype_id: str = ""

    def htc_computable(self) -> bool:
        """True when all U-values and q50 are set (non-zero)."""
        return all([
            self.u_wall, self.u_roof, self.u_floor,
            self.u_window, self.u_door, self.q50,
        ])


_C_AIR = 0.33  # Wh/m³K — volumetric heat capacity of air


def derived_quantities(p: DwellingParams) -> dict:
    """Compute HTC, tau, and envelope geometry from a DwellingParams instance."""
    footprint = p.total_floor_area_m2 / 2.0  # two-storey assumption; bungalows not supported
    aspect = p.plan_aspect_ratio
    width = (footprint / aspect) ** 0.5
    length = width * aspect
    perimeter = 2.0 * (length + width)
    wall_gross = perimeter * p.storey_height_m * 2.0
    wall_net = wall_gross - p.window_area_m2 - p.door_area_m2
    assert wall_net >= 0, (
        f"window+door area ({p.window_area_m2 + p.door_area_m2:.1f} m²) "
        f"exceeds gross wall area ({wall_gross:.1f} m²)"
    )
    roof_area = footprint
    floor_area = footprint
    envelope_area = wall_gross + roof_area + floor_area
    volume = p.total_floor_area_m2 * p.storey_height_m

    fabric_htc = (
        p.u_wall   * wall_net +
        p.u_roof   * roof_area +
        p.u_floor  * floor_area +
        p.u_window * p.window_area_m2 +
        p.u_door   * p.door_area_m2
    )
    bridging_htc = p.y_value * envelope_area
    leakage_50pa = p.q50 * envelope_area
    n50 = leakage_50pa / volume
    ach_natural = n50 / 20.0
    ventilation_htc = _C_AIR * ach_natural * volume

    htc = fabric_htc + bridging_htc + ventilation_htc
    c_wh_per_k = p.kappa * p.total_floor_area_m2
    tau_hours = c_wh_per_k / htc

    return {
        "footprint_m2":     footprint,
        "wall_gross_m2":    wall_gross,
        "wall_net_m2":      wall_net,
        "roof_area_m2":     roof_area,
        "floor_area_m2":    floor_area,
        "envelope_area_m2": envelope_area,
        "volume_m3":        volume,
        "ach_natural":      ach_natural,
        "fabric_htc":       fabric_htc,
        "bridging_htc":     bridging_htc,
        "ventilation_htc":  ventilation_htc,
        "htc":              htc,
        "c_wh_per_k":       c_wh_per_k,
        "tau_hours":        tau_hours,
    }


ARCHETYPES: dict[str, dict] = {
    "pre-1919-terraced": {
        "archetype_id":        "pre-1919-terraced",
        "label":               "Pre-1919 solid brick terraced",
        "total_floor_area_m2": 75.0,
        "storey_height_m":     2.7,
        "window_area_m2":      10.0,
        "door_area_m2":         3.0,
        "u_wall":               1.70,
        "u_roof":               0.16,
        "u_floor":              0.70,
        "u_window":             1.80,
        "u_door":               2.00,
        "y_value":              0.15,
        "q50":                 14.0,
        "kappa":              220.0,
        "sensor_elec_meter":   True,
        "sensor_gas_meter":    True,
        "sensor_outdoor_temp": True,
        "sensor_wind_speed":   True,
    },
    "1970s-semi": {
        "archetype_id":        "1970s-semi",
        "label":               "1970s semi, unimproved",
        "total_floor_area_m2": 85.0,
        "storey_height_m":     2.4,
        "window_area_m2":      14.0,
        "door_area_m2":         3.6,
        "u_wall":               0.60,
        "u_roof":               0.35,
        "u_floor":              0.70,
        "u_window":             2.80,
        "u_door":               3.00,
        "y_value":              0.15,
        "q50":                 10.0,
        "kappa":              160.0,
        "sensor_elec_meter":   True,
        "sensor_gas_meter":    True,
        "sensor_outdoor_temp": True,
        "sensor_wind_speed":   True,
    },
    "1990s-semi": {
        "archetype_id":        "1990s-semi",
        "label":               "1990s semi, partial upgrade",
        "total_floor_area_m2": 90.0,
        "storey_height_m":     2.4,
        "window_area_m2":      16.0,
        "door_area_m2":         3.6,
        "u_wall":               0.60,
        "u_roof":               0.16,
        "u_floor":              0.45,
        "u_window":             1.80,
        "u_door":               1.80,
        "y_value":              0.09,
        "q50":                  8.0,
        "kappa":              160.0,
        "sensor_elec_meter":   True,
        "sensor_gas_meter":    True,
        "sensor_outdoor_temp": True,
        "sensor_wind_speed":   True,
    },
    "2005-detached": {
        "archetype_id":        "2005-detached",
        "label":               "2005 detached, Part L 2002",
        "total_floor_area_m2": 130.0,
        "storey_height_m":     2.4,
        "window_area_m2":      22.0,
        "door_area_m2":         4.0,
        "u_wall":               0.35,
        "u_roof":               0.16,
        "u_floor":              0.25,
        "u_window":             1.60,
        "u_door":               1.40,
        "y_value":              0.08,
        "q50":                  6.0,
        "kappa":              155.0,
        "sensor_elec_meter":   True,
        "sensor_gas_meter":    True,
        "sensor_outdoor_temp": True,
        "sensor_wind_speed":   True,
        "sensor_indoor_temp":  True,
        "sensor_solar_generation": True,
    },
    "2015-semi": {
        "archetype_id":        "2015-semi",
        "label":               "2015 semi, Part L 2013",
        "total_floor_area_m2": 88.0,
        "storey_height_m":     2.4,
        "window_area_m2":      15.0,
        "door_area_m2":         3.6,
        "u_wall":               0.28,
        "u_roof":               0.13,
        "u_floor":              0.20,
        "u_window":             1.40,
        "u_door":               1.20,
        "y_value":              0.05,
        "q50":                  4.0,
        "kappa":              145.0,
        "sensor_elec_meter":   True,
        "sensor_gas_meter":    True,
        "sensor_outdoor_temp": True,
        "sensor_wind_speed":   True,
    },
}


def create_dwelling(archetype_id: str, **overrides) -> DwellingParams:
    """Create a DwellingParams from a named archetype with optional field overrides."""
    if archetype_id not in ARCHETYPES:
        raise ValueError(
            f"Unknown archetype: '{archetype_id}'. "
            f"Valid: {sorted(ARCHETYPES)}"
        )
    params = dict(ARCHETYPES[archetype_id])
    params.update(overrides)
    return DwellingParams(**params)


_TIER_SENSORS: dict[int, frozenset[str]] = {
    1: frozenset({
        "sensor_elec_meter", "sensor_gas_meter",
    }),
    2: frozenset({
        "sensor_elec_meter", "sensor_gas_meter",
        "sensor_outdoor_temp", "sensor_wind_speed",
    }),
    3: frozenset({
        "sensor_elec_meter", "sensor_gas_meter",
        "sensor_outdoor_temp", "sensor_wind_speed",
        "sensor_occupancy",
    }),
    4: frozenset({
        "sensor_elec_meter", "sensor_gas_meter",
        "sensor_outdoor_temp", "sensor_wind_speed",
        "sensor_occupancy", "sensor_indoor_temp",
    }),
    5: frozenset({
        "sensor_elec_meter", "sensor_gas_meter",
        "sensor_outdoor_temp", "sensor_wind_speed",
        "sensor_occupancy", "sensor_indoor_temp",
        "sensor_solar_generation", "sensor_battery_state",
    }),
}


def validate_sensor_tier(p: DwellingParams, tier: int) -> tuple[bool, list[str]]:
    """
    Check whether a dwelling meets the sensor prerequisite for a given tier.

    Returns (ok, missing) where ok is True when all required sensors are
    present and missing is the list of sensor field names that are False.
    """
    if tier not in _TIER_SENSORS:
        raise ValueError(f"Unknown tier {tier}. Valid: {sorted(_TIER_SENSORS)}")
    missing = sorted(s for s in _TIER_SENSORS[tier] if not getattr(p, s))
    return len(missing) == 0, missing

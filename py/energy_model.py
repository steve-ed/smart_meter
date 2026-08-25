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


_C_AIR = 0.33  # Wh/m³K — volumetric heat capacity of air


def derived_quantities(p: DwellingParams) -> dict:
    """Compute HTC, tau, and envelope geometry from a DwellingParams instance."""
    footprint = p.total_floor_area_m2 / 2.0
    aspect = p.plan_aspect_ratio
    width = (footprint / aspect) ** 0.5
    length = width * aspect
    perimeter = 2.0 * (length + width)
    wall_gross = perimeter * p.storey_height_m * 2.0
    wall_net = wall_gross - p.window_area_m2 - p.door_area_m2
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

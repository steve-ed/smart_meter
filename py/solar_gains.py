from __future__ import annotations
import math

_SOLAR_CONSTANT_W_M2 = 1353.0
_BIRMINGHAM_LAT_RAD = math.radians(52.48)
_MIN_ELEVATION_RAD = math.radians(3.0)

# Monthly clearness indices (Birmingham/Sheffield approximation).
# Clearness = actual sunshine hours / max possible daylength.
_CLEARNESS: dict[int, float] = {
    1: 0.24, 2: 0.31, 3: 0.37, 4: 0.39, 5: 0.41, 6: 0.43,
    7: 0.43, 8: 0.45, 9: 0.40, 10: 0.34, 11: 0.26, 12: 0.21,
}

# Surface azimuths from south, positive west (standard solar convention).
_SURFACE_AZIMUTHS_RAD: dict[str, float] = {
    "N": math.pi,
    "S": 0.0,
    "E": -math.pi / 2,
    "W": math.pi / 2,
}


def _day_of_year(date_str: str) -> int:
    year, month, day = int(date_str[:4]), int(date_str[5:7]), int(date_str[8:10])
    days = [0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    if (year % 4 == 0 and year % 100 != 0) or year % 400 == 0:
        days[2] = 29
    return sum(days[:month]) + day


def _solar_position(timestamp: str) -> tuple[float, float, int]:
    """Return (elevation_rad, azimuth_rad_from_south_positive_west, month)."""
    h, m = int(timestamp[11:13]), int(timestamp[14:16])
    hour_frac = h + (m + 15) / 60.0  # midpoint of half-hour slot
    doy = _day_of_year(timestamp[:10])
    month = int(timestamp[5:7])
    lat = _BIRMINGHAM_LAT_RAD
    declination = math.radians(23.45 * math.sin(math.radians(360 / 365 * (doy - 81))))
    hour_angle = math.radians(15.0 * (hour_frac - 12.0))
    sin_elev = max(-1.0, min(1.0,
        math.sin(lat) * math.sin(declination)
        + math.cos(lat) * math.cos(declination) * math.cos(hour_angle)
    ))
    elev = math.asin(sin_elev)
    cos_elev = math.cos(elev)
    if cos_elev < 1e-6:
        return elev, 0.0, month
    sin_az = math.cos(declination) * math.sin(hour_angle) / cos_elev
    cos_az = (sin_elev * math.sin(lat) - math.sin(declination)) / (cos_elev * math.cos(lat))
    return elev, math.atan2(sin_az, cos_az), month


def _dni_clear_sky(sin_elev: float) -> float:
    am = min(1.0 / sin_elev, 10.0)
    return _SOLAR_CONSTANT_W_M2 * (0.7 ** (am ** 0.678))


def surface_irradiance_w_per_m2(
    timestamp: str,
    orientation: str = "S",
) -> float:
    """Clear-sky irradiance on a vertical surface of given orientation (W/m²).

    Uses Sheffield latitude (53.4°N). Returns the theoretical clear-sky value
    without cloud correction. Returns 0.0 when sun is below 3° elevation.
    A south-facing vertical surface peaks in winter (low sun angle hits it
    more directly) which is the correct shape for UK glazing gain modelling.
    """
    elev, az, month = _solar_position(timestamp)
    if elev < _MIN_ELEVATION_RAD:
        return 0.0
    sin_e = math.sin(elev)
    dni = _dni_clear_sky(sin_e)
    surface_az = _SURFACE_AZIMUTHS_RAD.get(orientation, 0.0)
    cos_incidence = math.cos(elev) * math.cos(az - surface_az)
    direct = max(0.0, dni * cos_incidence)
    diffuse = 0.5 * 0.10 * dni * sin_e  # sky-view factor × diffuse fraction for vertical surface
    return max(0.0, direct + diffuse)


def compute_orientation_irradiance(
    timestamps: list[str],
    orientations: dict[str, float],
) -> dict[str, dict[str, float]]:
    """Compute cloud-corrected irradiance (W/m²) per orientation for each timestamp.

    Applies monthly clearness indices to scale clear-sky values for Sheffield.
    Returns {timestamp: {orientation: irradiance_w_m2}}.
    orientations keys are the directions to compute; values (fractions) are ignored here.
    """
    result: dict[str, dict[str, float]] = {}
    for ts in timestamps:
        month = int(ts[5:7])
        clearness = _CLEARNESS[month]
        result[ts] = {
            o: surface_irradiance_w_per_m2(ts, o) * clearness
            for o in orientations
        }
    return result

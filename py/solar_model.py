from datetime import date
from energy_model import DwellingParams
from solar_profile import get_pvgis_profile


def generate_solar_profile(
    p: DwellingParams,
    lat: float,
    lon: float,
    year: int = 2020,
    cache_dir: str = "data",
) -> dict[date, list[float]] | None:
    """
    Generate half-hourly solar generation (kWh) for a dwelling.

    Returns None if p.solar_present is False.

    Calls get_pvgis_profile with the dwelling's tilt and azimuth, then
    scales each slot by peak_kw x performance_ratio.

    Returns dict[date, list[48 float]] -- kWh per half-hour.
    """
    if not p.solar_present:
        return None

    pvgis = get_pvgis_profile(
        lat=lat,
        lon=lon,
        tilt=p.solar_tilt_deg,
        azimuth=p.solar_azimuth_deg,
        year=year,
        cache_dir=cache_dir,
    )
    scale = p.solar_peak_kw * p.solar_performance_ratio
    return {d: [s * scale for s in slots] for d, slots in pvgis.items()}

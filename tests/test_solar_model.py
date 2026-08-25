import pytest
from datetime import date, timedelta
from unittest.mock import patch
from solar_model import generate_solar_profile
from energy_model import create_dwelling


def _uniform_pvgis(kwh_per_slot: float, year: int = 2020) -> dict:
    """Return a PVGIS profile where every slot of every day has kwh_per_slot."""
    start = date(year, 1, 1)
    days = 366 if year % 4 == 0 else 365
    return {start + timedelta(days=i): [kwh_per_slot] * 48 for i in range(days)}


def test_generate_solar_profile_returns_none_when_no_solar():
    p = create_dwelling("1970s-semi")  # solar_present=False by default
    result = generate_solar_profile(p, lat=53.6, lon=-1.32)
    assert result is None


def test_generate_solar_profile_returns_dict_when_solar_present(tmp_path):
    mock_profile = {date(2020, 6, 1): [0.5] * 48}
    with patch("solar_model.get_pvgis_profile", return_value=mock_profile):
        p = create_dwelling(
            "2005-detached",
            solar_present=True,
            solar_peak_kw=4.0,
            solar_performance_ratio=0.8,
        )
        result = generate_solar_profile(p, lat=53.6, lon=-1.32)

    assert result is not None
    assert date(2020, 6, 1) in result
    assert len(result[date(2020, 6, 1)]) == 48


def test_generate_solar_profile_scales_by_peak_kw():
    """Each slot must equal pvgis_slot x peak_kw x performance_ratio."""
    mock_profile = {date(2020, 6, 1): [0.5] * 48}
    with patch("solar_model.get_pvgis_profile", return_value=mock_profile):
        p = create_dwelling(
            "2005-detached",
            solar_present=True,
            solar_peak_kw=4.0,
            solar_performance_ratio=1.0,
        )
        result = generate_solar_profile(p, lat=53.6, lon=-1.32)

    # 0.5 x 4.0 x 1.0 = 2.0 kWh per slot
    assert result[date(2020, 6, 1)][0] == pytest.approx(2.0)


def test_generate_solar_profile_scales_by_performance_ratio():
    mock_profile = {date(2020, 6, 1): [0.5] * 48}
    with patch("solar_model.get_pvgis_profile", return_value=mock_profile):
        p = create_dwelling(
            "2005-detached",
            solar_present=True,
            solar_peak_kw=1.0,
            solar_performance_ratio=0.75,
        )
        result = generate_solar_profile(p, lat=53.6, lon=-1.32)

    # 0.5 x 1.0 x 0.75 = 0.375 kWh per slot
    assert result[date(2020, 6, 1)][0] == pytest.approx(0.375)


def test_generate_solar_profile_uses_dwelling_tilt_and_azimuth():
    """generate_solar_profile must pass solar_tilt_deg and solar_azimuth_deg to PVGIS."""
    mock_profile = {date(2020, 6, 1): [0.1] * 48}
    with patch("solar_model.get_pvgis_profile", return_value=mock_profile) as mock_pvgis:
        p = create_dwelling(
            "2005-detached",
            solar_present=True,
            solar_peak_kw=3.0,
            solar_tilt_deg=30.0,
            solar_azimuth_deg=160.0,
            solar_performance_ratio=0.8,
        )
        generate_solar_profile(p, lat=53.6, lon=-1.32)

    call_kwargs = mock_pvgis.call_args.kwargs
    assert call_kwargs["tilt"] == pytest.approx(30.0)
    assert call_kwargs["azimuth"] == pytest.approx(160.0)


def test_generate_solar_profile_annual_fidelity():
    """Annual yield must be within +-5% of pvgis_annual x peak_kw x PR."""
    # Uniform PVGIS profile totalling 900 kWh/kWp/yr over 366 days (2020 is a leap year)
    kwh_per_slot = 900.0 / 366.0 / 48.0
    mock_profile = _uniform_pvgis(kwh_per_slot, year=2020)

    with patch("solar_model.get_pvgis_profile", return_value=mock_profile):
        p = create_dwelling(
            "2005-detached",
            solar_present=True,
            solar_peak_kw=3.5,
            solar_performance_ratio=0.8,
        )
        result = generate_solar_profile(p, lat=53.6, lon=-1.32)

    annual = sum(sum(slots) for slots in result.values())
    expected = 900.0 * 3.5 * 0.8  # 2520 kWh/yr
    assert annual == pytest.approx(expected, rel=0.05)


def test_generate_solar_profile_non_negative():
    mock_profile = {date(2020, 6, 1): [0.0, 0.5, 1.0, 0.0] + [0.0] * 44}
    with patch("solar_model.get_pvgis_profile", return_value=mock_profile):
        p = create_dwelling(
            "2005-detached",
            solar_present=True,
            solar_peak_kw=4.0,
            solar_performance_ratio=0.8,
        )
        result = generate_solar_profile(p, lat=53.6, lon=-1.32)

    assert all(v >= 0.0 for v in result[date(2020, 6, 1)])


def test_generate_solar_profile_passes_lat_lon_year_cache_dir(tmp_path):
    """lat, lon, year, and cache_dir must be forwarded to get_pvgis_profile."""
    mock_profile = {date(2021, 6, 1): [0.1] * 48}
    with patch("solar_model.get_pvgis_profile", return_value=mock_profile) as mock_pvgis:
        p = create_dwelling(
            "2005-detached",
            solar_present=True,
            solar_peak_kw=3.0,
            solar_performance_ratio=0.8,
        )
        generate_solar_profile(p, lat=51.5, lon=-0.1, year=2021, cache_dir=str(tmp_path))

    call_kwargs = mock_pvgis.call_args.kwargs
    assert call_kwargs["lat"] == pytest.approx(51.5)
    assert call_kwargs["lon"] == pytest.approx(-0.1)
    assert call_kwargs["year"] == 2021
    assert call_kwargs["cache_dir"] == str(tmp_path)

import json
import os
import pytest
from datetime import date, timedelta
from unittest.mock import patch, MagicMock
from solar_profile import get_pvgis_profile


def _make_pvgis_response(slots_with_watts):
    """Build a minimal PVGIS hourly response. slots_with_watts: {(month, day, hour): watts}"""
    hourly = []
    for (month, day, hour), watts in slots_with_watts.items():
        hourly.append({"time": f"2023{month:02d}{day:02d}:{hour:02d}10", "P": watts})
    return {"outputs": {"hourly": hourly}}


def test_pvgis_profile_converts_watts_to_halfhourly_kwh_per_kwp(tmp_path):
    """
    PVGIS returns hourly P in Watts for 1 kWp.
    500W at noon on June 1 → 500/1000/2 = 0.25 kWh per half-hourly slot per kWp.
    Both slot 24 (12:00) and slot 25 (12:30) should be 0.25.
    Nighttime (hour 0) should be 0.0.
    """
    mock_data = _make_pvgis_response({
        (6, 1, 0): 0.0,
        (6, 1, 12): 500.0,
        (6, 1, 13): 400.0,
    })
    with patch("solar_profile.requests.get") as mock_get:
        mock_get.return_value.json.return_value = mock_data
        mock_get.return_value.raise_for_status = MagicMock()
        profile = get_pvgis_profile(lat=51.5, lon=-0.1, tilt=35, azimuth=180,
                                    year=2023, cache_dir=str(tmp_path))

    assert date(2023, 6, 1) in profile
    slots = profile[date(2023, 6, 1)]
    assert len(slots) == 48
    assert slots[0] == pytest.approx(0.0)    # midnight
    assert slots[1] == pytest.approx(0.0)    # 00:30
    assert slots[24] == pytest.approx(0.25)  # 12:00
    assert slots[25] == pytest.approx(0.25)  # 12:30
    assert slots[26] == pytest.approx(0.20)  # 13:00 (400W)
    assert slots[27] == pytest.approx(0.20)  # 13:30


def test_pvgis_profile_caches_and_avoids_second_api_call(tmp_path):
    """Second call with same lat/lon/year must use cache, not hit the API again."""
    mock_data = _make_pvgis_response({(6, 1, 12): 300.0})
    with patch("solar_profile.requests.get") as mock_get:
        mock_get.return_value.json.return_value = mock_data
        mock_get.return_value.raise_for_status = MagicMock()
        get_pvgis_profile(lat=51.5, lon=-0.1, cache_dir=str(tmp_path))
        get_pvgis_profile(lat=51.5, lon=-0.1, cache_dir=str(tmp_path))
        assert mock_get.call_count == 1

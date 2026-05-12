"""Test the Offdelay weather sensor and coordinator weather logic."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.offdelay.const import DOMAIN

from .const import MOCK_CONFIG


async def _setup_entry(
    hass: HomeAssistant, config: dict | None = None
) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, data=config or MOCK_CONFIG)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_fetch_weather_slice_hourly_forecast(hass: HomeAssistant):
    """Test weather data extraction from hourly forecast."""
    hass.states.async_set("weather.home", "sunny")

    mock_now = datetime(2026, 5, 1, 12, 0, 0, tzinfo=dt_util.UTC)

    hourly_forecast = {
        "weather.home": {
            "forecast": [
                {"datetime": "2026-05-01T12:00:00+00:00", "temperature": 15.0},
                {"datetime": "2026-05-01T14:00:00+00:00", "temperature": 20.0},
                {"datetime": "2026-05-01T18:00:00+00:00", "temperature": 18.0},
            ]
        }
    }

    with (
        patch("homeassistant.util.dt.now", return_value=mock_now),
        patch(
            "homeassistant.core.ServiceRegistry.async_call",
            new_callable=AsyncMock,
            return_value=hourly_forecast,
        ) as mock_call,
    ):
        entry = await _setup_entry(hass)
        coordinator = entry.runtime_data.coordinator

        weather_data = await coordinator._fetch_weather_slice()

        assert weather_data == {
            "weather_max_temp_today": 20.0,
            "weather_min_temp_today": 15.0,
        }
        mock_call.assert_called_with(
            "weather",
            "get_forecasts",
            {"entity_id": "weather.home", "type": "hourly"},
            blocking=True,
            return_response=True,
        )


async def test_fetch_weather_slice_no_forecast(hass: HomeAssistant):
    """Test weather data extraction when no forecast is available."""
    hass.states.async_set("weather.home", "sunny")

    with patch(
        "homeassistant.core.ServiceRegistry.async_call",
        new_callable=AsyncMock,
        return_value={"weather.home": {}},
    ):
        entry = await _setup_entry(hass)
        coordinator = entry.runtime_data.coordinator

        weather_data = await coordinator._fetch_weather_slice()
        assert weather_data == {}


async def test_fetch_weather_slice_no_today_entries(hass: HomeAssistant):
    """Test weather data extraction when no entries for today are available."""
    hass.states.async_set("weather.home", "sunny")

    mock_now = datetime(2026, 5, 1, 12, 0, 0, tzinfo=dt_util.UTC)

    hourly_forecast = {
        "weather.home": {
            "forecast": [
                {"datetime": "2026-05-02T14:00:00+00:00", "temperature": 15.0},
                {"datetime": "2026-05-02T18:00:00+00:00", "temperature": 20.0},
            ]
        }
    }

    with (
        patch("homeassistant.util.dt.now", return_value=mock_now),
        patch(
            "homeassistant.core.ServiceRegistry.async_call",
            new_callable=AsyncMock,
            return_value=hourly_forecast,
        ),
    ):
        entry = await _setup_entry(hass)
        coordinator = entry.runtime_data.coordinator

        weather_data = await coordinator._fetch_weather_slice()
        assert weather_data == {}


async def test_fetch_weather_slice_multiple_days(hass: HomeAssistant):
    """Test weather data extraction filters out entries not for today."""
    hass.states.async_set("weather.home", "sunny")

    mock_now = datetime(2026, 5, 1, 12, 0, 0, tzinfo=dt_util.UTC)

    hourly_forecast = {
        "weather.home": {
            "forecast": [
                {"datetime": "2026-05-01T14:00:00+00:00", "temperature": 20.0},
                {"datetime": "2026-05-01T18:00:00+00:00", "temperature": 15.0},
                {"datetime": "2026-05-02T14:00:00+00:00", "temperature": 25.0},
                {"datetime": "2026-05-02T18:00:00+00:00", "temperature": 10.0},
            ]
        }
    }

    with (
        patch("homeassistant.util.dt.now", return_value=mock_now),
        patch(
            "homeassistant.core.ServiceRegistry.async_call",
            new_callable=AsyncMock,
            return_value=hourly_forecast,
        ),
    ):
        entry = await _setup_entry(hass)
        coordinator = entry.runtime_data.coordinator

        weather_data = await coordinator._fetch_weather_slice()

        assert weather_data == {
            "weather_max_temp_today": 20.0,
            "weather_min_temp_today": 15.0,
        }

"""Test the Offdelay night temperature sensor (multi-sensor min logic)."""

from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.offdelay.const import (
    CONF_SUMMER_NIGHT_MAX_TEMP,
    CONF_SUMMER_NIGHT_MIN_TEMP,
    CONF_SUMMER_NIGHT_TEMP_SENSOR,
    DOMAIN,
)

from .const import MOCK_CONFIG


@pytest.fixture(autouse=True)
def bypass_weather():
    """Bypass weather calls so coordinator setup doesn't hit network."""
    with patch(
        "custom_components.offdelay.coordinator.OffdelayDataUpdateCoordinator._fetch_weather_slice",
        new_callable=AsyncMock,
        return_value={
            "weather_max_temp_today": 20,
            "weather_min_temp_today": 10,
        },
    ):
        yield


async def _setup(hass: HomeAssistant, config: dict) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_empty_config_no_night_sensor_entity(hass: HomeAssistant) -> None:
    """Empty list = no night temp sensor entity created."""
    await _setup(hass, MOCK_CONFIG)
    assert hass.states.get("sensor.offdelay_summer_night_temp_reading") is None
    assert hass.states.get("sensor.offdelay_winter_night_temp_reading") is None


async def test_single_sensor_mirrors_source(hass: HomeAssistant) -> None:
    """Single sensor value is forwarded to coordinator data."""
    hass.states.async_set("sensor.outdoor_temp", "18.5")

    config = {
        **MOCK_CONFIG,
        CONF_SUMMER_NIGHT_TEMP_SENSOR: ["sensor.outdoor_temp"],
        CONF_SUMMER_NIGHT_MAX_TEMP: 25.0,
        CONF_SUMMER_NIGHT_MIN_TEMP: 18.0,
    }
    entry = await _setup(hass, config)
    coordinator = entry.runtime_data.coordinator

    assert coordinator.data["summer_night_temp_reading"] == 18.5


async def test_multi_sensor_uses_min(hass: HomeAssistant) -> None:
    """Min of multiple valid sensors is used."""
    hass.states.async_set("sensor.a", "19.0")
    hass.states.async_set("sensor.b", "17.5")
    hass.states.async_set("sensor.c", "18.2")

    config = {
        **MOCK_CONFIG,
        CONF_SUMMER_NIGHT_TEMP_SENSOR: ["sensor.a", "sensor.b", "sensor.c"],
        CONF_SUMMER_NIGHT_MAX_TEMP: 25.0,
        CONF_SUMMER_NIGHT_MIN_TEMP: 18.0,
    }
    entry = await _setup(hass, config)
    coordinator = entry.runtime_data.coordinator

    assert coordinator.data["summer_night_temp_reading"] == 17.5


async def test_partial_unavailable_uses_valid(hass: HomeAssistant) -> None:
    """Unavailable sensors are skipped; min of remaining valid is used."""
    hass.states.async_set("sensor.a", "unavailable")
    hass.states.async_set("sensor.b", "20.0")

    config = {
        **MOCK_CONFIG,
        CONF_SUMMER_NIGHT_TEMP_SENSOR: ["sensor.a", "sensor.b"],
        CONF_SUMMER_NIGHT_MAX_TEMP: 25.0,
        CONF_SUMMER_NIGHT_MIN_TEMP: 18.0,
    }
    entry = await _setup(hass, config)
    coordinator = entry.runtime_data.coordinator

    assert coordinator.data["summer_night_temp_reading"] == 20.0


async def test_all_unavailable_no_value_pushed(hass: HomeAssistant) -> None:
    """When all unavailable, coordinator key is not set / is None."""
    hass.states.async_set("sensor.a", "unavailable")
    hass.states.async_set("sensor.b", "unknown")

    config = {
        **MOCK_CONFIG,
        CONF_SUMMER_NIGHT_TEMP_SENSOR: ["sensor.a", "sensor.b"],
        CONF_SUMMER_NIGHT_MAX_TEMP: 25.0,
        CONF_SUMMER_NIGHT_MIN_TEMP: 18.0,
    }
    entry = await _setup(hass, config)
    coordinator = entry.runtime_data.coordinator

    assert coordinator.data.get("summer_night_temp_reading") is None


async def test_state_change_updates_min(hass: HomeAssistant) -> None:
    """Changing one source sensor recalculates min."""
    hass.states.async_set("sensor.a", "19.0")
    hass.states.async_set("sensor.b", "18.0")

    config = {
        **MOCK_CONFIG,
        CONF_SUMMER_NIGHT_TEMP_SENSOR: ["sensor.a", "sensor.b"],
        CONF_SUMMER_NIGHT_MAX_TEMP: 25.0,
        CONF_SUMMER_NIGHT_MIN_TEMP: 18.0,
    }
    entry = await _setup(hass, config)
    coordinator = entry.runtime_data.coordinator

    assert coordinator.data["summer_night_temp_reading"] == 18.0

    hass.states.async_set("sensor.b", "20.0")
    await hass.async_block_till_done()

    assert coordinator.data["summer_night_temp_reading"] == 19.0

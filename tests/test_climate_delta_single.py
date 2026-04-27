"""Delta single-value tests for Offdelay climate delta."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.offdelay.const import (
    DATA_CLIMATE_DELTA_TO_TARGET,
    DATA_CLIMATE_MODE,
    DOMAIN,
)

from .const import MOCK_CONFIG_WITH_CLIMATE


@pytest.fixture(autouse=True)
def bypass_weather():
    with patch(
        "custom_components.offdelay.coordinator.OffdelayDataUpdateCoordinator._update_weather_data",
        new_callable=AsyncMock,
        return_value={
            "weather_max_temp_today": 20,
            "weather_min_temp_today": 10,
            "weather_max_temp_tomorrow": 22,
            "weather_min_temp_tomorrow": 12,
        },
    ):
        yield


@pytest.fixture(autouse=True)
def force_night_window():
    mock_night = datetime(2026, 4, 24, 20, 0, 0, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.now", return_value=mock_night):
        yield


async def test_delta_winter_mode(hass: HomeAssistant):
    # living_room: current 22, target 20 -> delta -2
    # bedroom: current 18, target 21 -> delta +3
    # Winter selects most negative delta (warmest room vs target) = -2.0
    hass.states.async_set(
        "climate.living_room",
        "heat",
        {"current_temperature": 22.0, "temperature": 20.0},
    )
    hass.states.async_set(
        "climate.bedroom", "heat", {"current_temperature": 18.0, "temperature": 21.0}
    )
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_WITH_CLIMATE)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    coordinator = entry.runtime_data.coordinator
    coordinator.data[DATA_CLIMATE_MODE] = "winter"
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert coordinator.data[DATA_CLIMATE_DELTA_TO_TARGET] == pytest.approx(-2.0)


async def test_delta_summer_mode(hass: HomeAssistant):
    # living_room: current 22, target 20 -> delta -2
    # bedroom: current 18, target 21 -> delta +3
    # Summer selects most positive delta (coldest room vs target) = 3.0
    hass.states.async_set(
        "climate.living_room",
        "heat",
        {"current_temperature": 22.0, "temperature": 20.0},
    )
    hass.states.async_set(
        "climate.bedroom", "heat", {"current_temperature": 18.0, "temperature": 21.0}
    )
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_WITH_CLIMATE)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    coordinator = entry.runtime_data.coordinator
    coordinator.data[DATA_CLIMATE_MODE] = "summer"
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert coordinator.data[DATA_CLIMATE_DELTA_TO_TARGET] == pytest.approx(3.0)


async def test_delta_off_mode(hass: HomeAssistant):
    hass.states.async_set(
        "climate.living_room",
        "heat",
        {"current_temperature": 22.0, "temperature": 20.0},
    )
    hass.states.async_set(
        "climate.bedroom", "heat", {"current_temperature": 18.0, "temperature": 21.0}
    )
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_WITH_CLIMATE)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    coordinator = entry.runtime_data.coordinator
    coordinator.data[DATA_CLIMATE_MODE] = "off"
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    # deltas: -2 and +3 -> max abs is 3
    assert coordinator.data[DATA_CLIMATE_DELTA_TO_TARGET] == pytest.approx(3.0)


async def test_delta_off_mode_tie_break(hass: HomeAssistant):
    hass.states.async_set(
        "climate.living_room",
        "heat",
        {"current_temperature": 20.0, "temperature": 25.0},
    )
    hass.states.async_set(
        "climate.bedroom", "heat", {"current_temperature": 20.0, "temperature": 25.0}
    )
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_WITH_CLIMATE)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    coordinator = entry.runtime_data.coordinator
    coordinator.data[DATA_CLIMATE_MODE] = "off"
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert coordinator.data[DATA_CLIMATE_DELTA_TO_TARGET] == pytest.approx(5.0)


async def test_delta_off_mode_mixed_zero_and_nonzero_tie_order(hass: HomeAssistant):
    # living_room delta = 0, bedroom delta = 4
    hass.states.async_set(
        "climate.living_room",
        "heat",
        {"current_temperature": 20.0, "temperature": 20.0},
    )
    hass.states.async_set(
        "climate.bedroom", "heat", {"current_temperature": 24.0, "temperature": 28.0}
    )
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_WITH_CLIMATE)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    coordinator = entry.runtime_data.coordinator
    coordinator.data[DATA_CLIMATE_MODE] = "off"
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert coordinator.data[DATA_CLIMATE_DELTA_TO_TARGET] == pytest.approx(4.0)


async def test_delta_off_mode_equal_deltas_tie_by_order(hass: HomeAssistant):
    # living_room delta = 5, bedroom delta = 5
    hass.states.async_set(
        "climate.living_room",
        "heat",
        {"current_temperature": 20.0, "temperature": 25.0},
    )
    hass.states.async_set(
        "climate.bedroom", "heat", {"current_temperature": 20.0, "temperature": 25.0}
    )
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_WITH_CLIMATE)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    coordinator = entry.runtime_data.coordinator
    coordinator.data[DATA_CLIMATE_MODE] = "off"
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert coordinator.data[DATA_CLIMATE_DELTA_TO_TARGET] == pytest.approx(5.0)

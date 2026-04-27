"""Test the Off-delay climate mode feature."""

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

from .const import MOCK_CONFIG, MOCK_CONFIG_WITH_CLIMATE


@pytest.fixture(autouse=True)
def bypass_weather():
    """Bypass weather calls."""
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


# A. Config Flow Validation Tests


async def test_config_flow_winter_summer_temp_conflict(hass: HomeAssistant):
    """Test that winter >= summer shows error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "winter_max_temp": 25,
            "summer_min_temp": 20,
            "climate_day_start_hour": 8,
            "climate_night_start_hour": 17,
            "climate_delta_tolerance": 0.5,
        },
    )
    assert result["errors"]["base"] == "winter_summer_temp_conflict"


async def test_config_flow_winter_summer_temp_too_close(hass: HomeAssistant):
    """Test that difference <= 0.1 shows error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "winter_max_temp": 19.95,
            "summer_min_temp": 20.0,
            "climate_day_start_hour": 8,
            "climate_night_start_hour": 17,
            "climate_delta_tolerance": 0.5,
        },
    )
    assert result["errors"]["base"] == "winter_summer_temp_too_close"


async def test_config_flow_valid_climate_config(hass: HomeAssistant):
    """Test valid config succeeds."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_CONFIG_WITH_CLIMATE,
    )
    assert result["type"] == "create_entry"


async def test_config_flow_day_night_hour_conflict(hass: HomeAssistant):
    """Test that day_start >= night_start shows error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "winter_max_temp": 15.0,
            "summer_min_temp": 20.0,
            "climate_day_start_hour": 17,
            "climate_night_start_hour": 8,
            "climate_delta_tolerance": 0.5,
        },
    )
    assert result["errors"]["base"] == "day_night_hour_conflict"


# B. Coordinator Climate Delta Tests


async def test_climate_delta_calculation(hass: HomeAssistant):
    """Test delta calculation with mock climate entities."""
    # Pin to day window so weather mode is used (mode="none" → delta selected as OFF)
    mock_day = datetime(2026, 4, 24, 12, 0, 0, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.now", return_value=mock_day):
        # Set up climate entities with known temps
        hass.states.async_set(
            "climate.living_room",
            "heat",
            {
                "current_temperature": 22.0,
                "temperature": 20.0,
            },
        )
        hass.states.async_set(
            "climate.bedroom",
            "heat",
            {
                "current_temperature": 18.0,
                "temperature": 21.0,
            },
        )

        entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_WITH_CLIMATE)
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        coordinator = entry.runtime_data.coordinator
        await coordinator.async_refresh()
        await hass.async_block_till_done()

        # Mode is "none" (weather: 20 is between winter_max=15 and summer_min=20)
        # Delta selection falls through to OFF mode: largest abs = 3.0 (bedroom)
        assert coordinator.data[DATA_CLIMATE_DELTA_TO_TARGET] == pytest.approx(3.0)


async def test_climate_delta_missing_entity(hass: HomeAssistant):
    """Test delta when a climate entity is unavailable."""
    mock_day = datetime(2026, 4, 24, 12, 0, 0, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.now", return_value=mock_day):
        # Only set up one of the two configured entities
        hass.states.async_set(
            "climate.living_room",
            "heat",
            {
                "current_temperature": 22.0,
                "temperature": 20.0,
            },
        )

        entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_WITH_CLIMATE)
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        coordinator = entry.runtime_data.coordinator
        await coordinator.async_refresh()
        await hass.async_block_till_done()

        # Only living_room has data: delta = 20 - 22 = -2.0
        # Mode is "none" → falls through to OFF → single delta = -2.0
        assert coordinator.data[DATA_CLIMATE_DELTA_TO_TARGET] == pytest.approx(-2.0)


# C. Coordinator Climate Mode Tests — Time Window Logic


async def test_weather_mode_during_day_window(hass: HomeAssistant):
    """Test weather logic runs during day window (10am, within 8-17)."""
    mock_now = datetime(2026, 4, 24, 10, 0, 0, tzinfo=dt_util.UTC)
    with (
        patch("homeassistant.util.dt.now", return_value=mock_now),
        patch(
            "custom_components.offdelay.coordinator.OffdelayDataUpdateCoordinator._update_weather_data",
            new_callable=AsyncMock,
            return_value={
                "weather_max_temp_today": 10,  # < winter_max_temp=15
                "weather_min_temp_today": 5,
                "weather_max_temp_tomorrow": 12,
                "weather_min_temp_tomorrow": 7,
            },
        ),
    ):
        entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_WITH_CLIMATE)
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        coordinator = entry.runtime_data.coordinator
        await coordinator.async_refresh()
        await hass.async_block_till_done()

        assert coordinator.data[DATA_CLIMATE_MODE] == "winter"


async def test_weather_mode_during_day_window_summer(hass: HomeAssistant):
    """Test weather logic sets summer during day window (14:00)."""
    mock_now = datetime(2026, 4, 24, 14, 0, 0, tzinfo=dt_util.UTC)
    with (
        patch("homeassistant.util.dt.now", return_value=mock_now),
        patch(
            "custom_components.offdelay.coordinator.OffdelayDataUpdateCoordinator._update_weather_data",
            new_callable=AsyncMock,
            return_value={
                "weather_max_temp_today": 25,  # > summer_min_temp=20
                "weather_min_temp_today": 15,
                "weather_max_temp_tomorrow": 22,
                "weather_min_temp_tomorrow": 12,
            },
        ),
    ):
        entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_WITH_CLIMATE)
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        coordinator = entry.runtime_data.coordinator
        await coordinator.async_refresh()
        await hass.async_block_till_done()

        assert coordinator.data[DATA_CLIMATE_MODE] == "summer"


async def test_climate_mode_during_night_window(hass: HomeAssistant):
    """Test climate entity logic runs during night window (20:00)."""
    # First set mode to "winter" during day window
    mock_day = datetime(2026, 4, 24, 10, 0, 0, tzinfo=dt_util.UTC)
    with (
        patch("homeassistant.util.dt.now", return_value=mock_day),
        patch(
            "custom_components.offdelay.coordinator.OffdelayDataUpdateCoordinator._update_weather_data",
            new_callable=AsyncMock,
            return_value={
                "weather_max_temp_today": 10,
                "weather_min_temp_today": 5,
                "weather_max_temp_tomorrow": 12,
                "weather_min_temp_tomorrow": 7,
            },
        ),
    ):
        entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_WITH_CLIMATE)
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        coordinator = entry.runtime_data.coordinator
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert coordinator.data[DATA_CLIMATE_MODE] == "winter"

    # Now at night (20:00), all climate entities are warm → winter transitions to off
    # tolerance is 0.5 in MOCK_CONFIG_WITH_CLIMATE
    hass.states.async_set(
        "climate.living_room",
        "heat",
        {"current_temperature": 22.0, "temperature": 20.0},
    )
    hass.states.async_set(
        "climate.bedroom",
        "heat",
        {"current_temperature": 22.0, "temperature": 20.0},
    )

    mock_night = datetime(2026, 4, 24, 20, 0, 0, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.now", return_value=mock_night):
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert coordinator.data[DATA_CLIMATE_MODE] == "off"


async def test_weather_mode_all_day_no_climates(hass: HomeAssistant):
    """Test weather logic runs even at night when no climates configured."""
    mock_night = datetime(2026, 4, 24, 20, 0, 0, tzinfo=dt_util.UTC)
    with (
        patch("homeassistant.util.dt.now", return_value=mock_night),
        patch(
            "custom_components.offdelay.coordinator.OffdelayDataUpdateCoordinator._update_weather_data",
            new_callable=AsyncMock,
            return_value={
                "weather_max_temp_today": 10,  # < winter_max_temp defaults
                "weather_min_temp_today": 5,
                "weather_max_temp_tomorrow": 12,
                "weather_min_temp_tomorrow": 7,
            },
        ),
    ):
        # Use MOCK_CONFIG which has NO climates — need to add hour settings
        config = {
            **MOCK_CONFIG,
            "winter_max_temp": 15.0,
            "summer_min_temp": 20.0,
            "climate_day_start_hour": 8,
            "climate_night_start_hour": 17,
        }
        entry = MockConfigEntry(domain=DOMAIN, data=config)
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        coordinator = entry.runtime_data.coordinator
        await coordinator.async_refresh()
        await hass.async_block_till_done()

        # Weather logic should run even at night (no climates = weather 24/7)
        assert coordinator.data[DATA_CLIMATE_MODE] == "winter"


async def test_weather_mode_no_climates_summer(hass: HomeAssistant):
    """Test weather logic returns summer at night when no climates and hot forecast."""
    mock_night = datetime(2026, 4, 24, 22, 0, 0, tzinfo=dt_util.UTC)
    with (
        patch("homeassistant.util.dt.now", return_value=mock_night),
        patch(
            "custom_components.offdelay.coordinator.OffdelayDataUpdateCoordinator._update_weather_data",
            new_callable=AsyncMock,
            return_value={
                "weather_max_temp_today": 25,  # > summer_min_temp
                "weather_min_temp_today": 15,
                "weather_max_temp_tomorrow": 22,
                "weather_min_temp_tomorrow": 12,
            },
        ),
    ):
        config = {
            **MOCK_CONFIG,
            "winter_max_temp": 15.0,
            "summer_min_temp": 20.0,
            "climate_day_start_hour": 8,
            "climate_night_start_hour": 17,
        }
        entry = MockConfigEntry(domain=DOMAIN, data=config)
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        coordinator = entry.runtime_data.coordinator
        await coordinator.async_refresh()
        await hass.async_block_till_done()

        assert coordinator.data[DATA_CLIMATE_MODE] == "summer"


async def test_mode_persists_within_same_window(hass: HomeAssistant):
    """Test mode set during day window persists on subsequent day updates."""
    # Set winter at 9am
    mock_9am = datetime(2026, 4, 24, 9, 0, 0, tzinfo=dt_util.UTC)
    with (
        patch("homeassistant.util.dt.now", return_value=mock_9am),
        patch(
            "custom_components.offdelay.coordinator.OffdelayDataUpdateCoordinator._update_weather_data",
            new_callable=AsyncMock,
            return_value={
                "weather_max_temp_today": 10,
                "weather_min_temp_today": 5,
                "weather_max_temp_tomorrow": 12,
                "weather_min_temp_tomorrow": 7,
            },
        ),
    ):
        entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_WITH_CLIMATE)
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        coordinator = entry.runtime_data.coordinator
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert coordinator.data[DATA_CLIMATE_MODE] == "winter"

    # At 12pm, same weather → mode should still be winter
    mock_12pm = datetime(2026, 4, 24, 12, 0, 0, tzinfo=dt_util.UTC)
    with (
        patch("homeassistant.util.dt.now", return_value=mock_12pm),
        patch(
            "custom_components.offdelay.coordinator.OffdelayDataUpdateCoordinator._update_weather_data",
            new_callable=AsyncMock,
            return_value={
                "weather_max_temp_today": 10,
                "weather_min_temp_today": 5,
                "weather_max_temp_tomorrow": 12,
                "weather_min_temp_tomorrow": 7,
            },
        ),
    ):
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert coordinator.data[DATA_CLIMATE_MODE] == "winter"


async def test_boundary_hour_inclusive_start(hass: HomeAssistant):
    """Test day_start hour is inclusive — exactly at 8:00 runs weather logic."""
    mock_8am = datetime(2026, 4, 24, 8, 0, 0, tzinfo=dt_util.UTC)
    with (
        patch("homeassistant.util.dt.now", return_value=mock_8am),
        patch(
            "custom_components.offdelay.coordinator.OffdelayDataUpdateCoordinator._update_weather_data",
            new_callable=AsyncMock,
            return_value={
                "weather_max_temp_today": 10,
                "weather_min_temp_today": 5,
                "weather_max_temp_tomorrow": 12,
                "weather_min_temp_tomorrow": 7,
            },
        ),
    ):
        entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_WITH_CLIMATE)
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        coordinator = entry.runtime_data.coordinator
        await coordinator.async_refresh()
        await hass.async_block_till_done()

        # At exactly day_start (8), weather logic should run
        assert coordinator.data[DATA_CLIMATE_MODE] == "winter"


async def test_boundary_hour_exclusive_end(hass: HomeAssistant):
    """Test night_start hour is exclusive for day window — exactly at 17:00 runs climate logic."""
    # First set mode to "winter" during day
    mock_day = datetime(2026, 4, 24, 10, 0, 0, tzinfo=dt_util.UTC)
    with (
        patch("homeassistant.util.dt.now", return_value=mock_day),
        patch(
            "custom_components.offdelay.coordinator.OffdelayDataUpdateCoordinator._update_weather_data",
            new_callable=AsyncMock,
            return_value={
                "weather_max_temp_today": 10,
                "weather_min_temp_today": 5,
                "weather_max_temp_tomorrow": 12,
                "weather_min_temp_tomorrow": 7,
            },
        ),
    ):
        entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_WITH_CLIMATE)
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        coordinator = entry.runtime_data.coordinator
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert coordinator.data[DATA_CLIMATE_MODE] == "winter"

    # At exactly 17:00 (night_start), climate logic should run, NOT weather
    # Set climate entities warm → should switch from winter to off
    hass.states.async_set(
        "climate.living_room",
        "heat",
        {"current_temperature": 22.0, "temperature": 20.0},
    )
    hass.states.async_set(
        "climate.bedroom",
        "heat",
        {"current_temperature": 22.0, "temperature": 20.0},
    )

    mock_5pm = datetime(2026, 4, 24, 17, 0, 0, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.now", return_value=mock_5pm):
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        # Climate logic runs at 17:00 (not weather), winter → off
        assert coordinator.data[DATA_CLIMATE_MODE] == "off"


# D. Binary Sensor State Tests


async def test_climate_binary_sensors_created(hass: HomeAssistant):
    """Test climate binary sensors are created when climates configured."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_WITH_CLIMATE)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.offdelay_climate_mode_winter")
    assert hass.states.get("binary_sensor.offdelay_climate_mode_summer")
    assert hass.states.get("binary_sensor.offdelay_climate_mode_winter_summer")


async def test_climate_binary_sensors_created_without_climate_config(
    hass: HomeAssistant,
):
    """Test climate binary sensors ARE created even without climate config."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.offdelay_climate_mode_winter")
    assert hass.states.get("binary_sensor.offdelay_climate_mode_summer")
    assert hass.states.get("binary_sensor.offdelay_climate_mode_winter_summer")

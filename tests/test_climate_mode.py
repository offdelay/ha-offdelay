"""Test the Off-delay climate mode feature."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.offdelay.const import DATA_CLIMATE_MODE, DOMAIN

from .const import MOCK_CONFIG, MOCK_CONFIG_WITH_NIGHT_SENSORS


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
            "winter_day_max_temp": 25,
            "summer_day_min_temp": 20,
            "climate_day_start_hour": 8,
            "climate_night_start_hour": 17,
            "summer_night_temp_sensor": "sensor.summer_night_temp",
            "summer_night_max_temp": 20.0,
            "summer_night_min_temp": 20.0,
            "winter_night_temp_sensor": "sensor.winter_night_temp",
            "winter_night_max_temp": 20.0,
            "winter_night_min_temp": 20.0,
        },
    )
    assert result["errors"]["base"] == "winter_summer_temp_conflict"  # type: ignore


async def test_config_flow_valid_climate_config(hass: HomeAssistant):
    """Test valid config succeeds."""
    climate_keys = {
        "winter_day_max_temp",
        "summer_day_min_temp",
        "summer_night_temp_sensor",
        "summer_night_max_temp",
        "summer_night_min_temp",
        "winter_night_temp_sensor",
        "winter_night_max_temp",
        "winter_night_min_temp",
        "climate_day_start_hour",
        "climate_night_start_hour",
    }
    climate_input = {
        k: v for k, v in MOCK_CONFIG_WITH_NIGHT_SENSORS.items() if k in climate_keys
    }
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=climate_input,
    )
    assert result.get("step_id") == "presence"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "guest_turn_on_delay": 5,
            "guest_turn_off_delay": 15,
        },
    )
    assert result.get("step_id") == "energy"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )
    assert result.get("type") == "create_entry"


async def test_config_flow_day_night_hour_conflict(hass: HomeAssistant):
    """Test that day_start >= night_start shows error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "winter_day_max_temp": 15.0,
            "summer_day_min_temp": 20.0,
            "climate_day_start_hour": 17,
            "climate_night_start_hour": 8,
            "summer_night_temp_sensor": "sensor.summer_night_temp",
            "summer_night_max_temp": 20.0,
            "summer_night_min_temp": 20.0,
            "winter_night_temp_sensor": "sensor.winter_night_temp",
            "winter_night_max_temp": 20.0,
            "winter_night_min_temp": 20.0,
        },
    )
    assert result["errors"]["base"] == "day_night_hour_conflict"  # type: ignore


# B. Coordinator Climate Mode Tests — Time Window Logic


async def test_weather_mode_during_day_window(hass: HomeAssistant):
    """Test weather logic runs during day window (10am, within 8-17)."""
    mock_now = datetime(2026, 4, 24, 10, 0, 0, tzinfo=dt_util.UTC)
    with (
        patch("homeassistant.util.dt.now", return_value=mock_now),
        patch(
            "custom_components.offdelay.coordinator.OffdelayDataUpdateCoordinator._update_weather_data",
            new_callable=AsyncMock,
            return_value={
                "weather_max_temp_today": 10,
                "weather_min_temp_today": 5,
            },
        ),
    ):
        entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_WITH_NIGHT_SENSORS)
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
                "weather_max_temp_today": 25,
                "weather_min_temp_today": 15,
            },
        ),
    ):
        entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_WITH_NIGHT_SENSORS)
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        coordinator = entry.runtime_data.coordinator
        await coordinator.async_refresh()
        await hass.async_block_till_done()

        assert coordinator.data[DATA_CLIMATE_MODE] == "summer"


async def test_climate_mode_during_night_window(hass: HomeAssistant):
    """Test night sensor logic runs during night window (20:00)."""
    mock_day = datetime(2026, 4, 24, 10, 0, 0, tzinfo=dt_util.UTC)
    with (
        patch("homeassistant.util.dt.now", return_value=mock_day),
        patch(
            "custom_components.offdelay.coordinator.OffdelayDataUpdateCoordinator._update_weather_data",
            new_callable=AsyncMock,
            return_value={
                "weather_max_temp_today": 10,
                "weather_min_temp_today": 5,
            },
        ),
    ):
        entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_WITH_NIGHT_SENSORS)
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        coordinator = entry.runtime_data.coordinator
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert coordinator.data[DATA_CLIMATE_MODE] == "winter"

    # Night (20:00): winter_night_temp > max (20.0) -> off
    hass.states.async_set("sensor.winter_night_temp", "25.0")
    await hass.async_block_till_done()

    mock_night = datetime(2026, 4, 24, 20, 0, 0, tzinfo=dt_util.UTC)
    with (
        patch("homeassistant.util.dt.now", return_value=mock_night),
        patch(
            "custom_components.offdelay.coordinator.OffdelayDataUpdateCoordinator._update_weather_data",
            new_callable=AsyncMock,
            return_value={
                "weather_max_temp_today": 10,
                "weather_min_temp_today": 5,
            },
        ),
    ):
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert coordinator.data[DATA_CLIMATE_MODE] == "off"


async def test_weather_mode_all_day_no_climates(hass: HomeAssistant):
    """Test weather logic runs even at night when no night sensors configured."""
    mock_night = datetime(2026, 4, 24, 20, 0, 0, tzinfo=dt_util.UTC)
    with (
        patch("homeassistant.util.dt.now", return_value=mock_night),
        patch(
            "custom_components.offdelay.coordinator.OffdelayDataUpdateCoordinator._update_weather_data",
            new_callable=AsyncMock,
            return_value={
                "weather_max_temp_today": 10,
                "weather_min_temp_today": 5,
            },
        ),
    ):
        config = {
            **MOCK_CONFIG,
            "winter_day_max_temp": 15.0,
            "summer_day_min_temp": 20.0,
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

        assert coordinator.data[DATA_CLIMATE_MODE] == "winter"


async def test_weather_mode_no_climates_summer(hass: HomeAssistant):
    """Test weather logic returns summer at night when no night sensors and hot forecast."""
    mock_night = datetime(2026, 4, 24, 22, 0, 0, tzinfo=dt_util.UTC)
    with (
        patch("homeassistant.util.dt.now", return_value=mock_night),
        patch(
            "custom_components.offdelay.coordinator.OffdelayDataUpdateCoordinator._update_weather_data",
            new_callable=AsyncMock,
            return_value={
                "weather_max_temp_today": 25,
                "weather_min_temp_today": 15,
            },
        ),
    ):
        config = {
            **MOCK_CONFIG,
            "winter_day_max_temp": 15.0,
            "summer_day_min_temp": 20.0,
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
    mock_9am = datetime(2026, 4, 24, 9, 0, 0, tzinfo=dt_util.UTC)
    with (
        patch("homeassistant.util.dt.now", return_value=mock_9am),
        patch(
            "custom_components.offdelay.coordinator.OffdelayDataUpdateCoordinator._update_weather_data",
            new_callable=AsyncMock,
            return_value={
                "weather_max_temp_today": 10,
                "weather_min_temp_today": 5,
            },
        ),
    ):
        entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_WITH_NIGHT_SENSORS)
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        coordinator = entry.runtime_data.coordinator
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert coordinator.data[DATA_CLIMATE_MODE] == "winter"

    mock_12pm = datetime(2026, 4, 24, 12, 0, 0, tzinfo=dt_util.UTC)
    with (
        patch("homeassistant.util.dt.now", return_value=mock_12pm),
        patch(
            "custom_components.offdelay.coordinator.OffdelayDataUpdateCoordinator._update_weather_data",
            new_callable=AsyncMock,
            return_value={
                "weather_max_temp_today": 10,
                "weather_min_temp_today": 5,
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
            },
        ),
    ):
        entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_WITH_NIGHT_SENSORS)
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        coordinator = entry.runtime_data.coordinator
        await coordinator.async_refresh()
        await hass.async_block_till_done()

        assert coordinator.data[DATA_CLIMATE_MODE] == "winter"


async def test_boundary_hour_exclusive_end(hass: HomeAssistant):
    """Test night_start hour is exclusive for day window — exactly at 17:00 runs night logic."""
    mock_day = datetime(2026, 4, 24, 10, 0, 0, tzinfo=dt_util.UTC)
    with (
        patch("homeassistant.util.dt.now", return_value=mock_day),
        patch(
            "custom_components.offdelay.coordinator.OffdelayDataUpdateCoordinator._update_weather_data",
            new_callable=AsyncMock,
            return_value={
                "weather_max_temp_today": 10,
                "weather_min_temp_today": 5,
            },
        ),
    ):
        entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_WITH_NIGHT_SENSORS)
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        coordinator = entry.runtime_data.coordinator
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert coordinator.data[DATA_CLIMATE_MODE] == "winter"

    # At exactly 17:00 (night_start), night logic runs
    hass.states.async_set("sensor.winter_night_temp", "25.0")
    await hass.async_block_till_done()

    mock_5pm = datetime(2026, 4, 24, 17, 0, 0, tzinfo=dt_util.UTC)
    with (
        patch("homeassistant.util.dt.now", return_value=mock_5pm),
        patch(
            "custom_components.offdelay.coordinator.OffdelayDataUpdateCoordinator._update_weather_data",
            new_callable=AsyncMock,
            return_value={
                "weather_max_temp_today": 10,
                "weather_min_temp_today": 5,
            },
        ),
    ):
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert coordinator.data[DATA_CLIMATE_MODE] == "off"


# C. Night Mode Transition Tests


async def test_night_mode_summer_to_off(hass: HomeAssistant):
    """Test summer mode transitions to off when sensor below min temp."""
    mock_day = datetime(2026, 4, 24, 14, 0, 0, tzinfo=dt_util.UTC)
    with (
        patch("homeassistant.util.dt.now", return_value=mock_day),
        patch(
            "custom_components.offdelay.coordinator.OffdelayDataUpdateCoordinator._update_weather_data",
            new_callable=AsyncMock,
            return_value={
                "weather_max_temp_today": 25,
                "weather_min_temp_today": 15,
            },
        ),
    ):
        entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_WITH_NIGHT_SENSORS)
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        coordinator = entry.runtime_data.coordinator
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert coordinator.data[DATA_CLIMATE_MODE] == "summer"

    # Night: summer_night_temp < min (20.0) -> off
    hass.states.async_set("sensor.summer_night_temp", "15.0")
    await hass.async_block_till_done()

    mock_night = datetime(2026, 4, 24, 20, 0, 0, tzinfo=dt_util.UTC)
    with (
        patch("homeassistant.util.dt.now", return_value=mock_night),
        patch(
            "custom_components.offdelay.coordinator.OffdelayDataUpdateCoordinator._update_weather_data",
            new_callable=AsyncMock,
            return_value={
                "weather_max_temp_today": 25,
                "weather_min_temp_today": 15,
            },
        ),
    ):
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert coordinator.data[DATA_CLIMATE_MODE] == "off"


async def test_night_mode_off_to_summer(hass: HomeAssistant):
    """Test off mode transitions to summer when sensor above max temp."""
    mock_day = datetime(2026, 4, 24, 14, 0, 0, tzinfo=dt_util.UTC)
    with (
        patch("homeassistant.util.dt.now", return_value=mock_day),
        patch(
            "custom_components.offdelay.coordinator.OffdelayDataUpdateCoordinator._update_weather_data",
            new_callable=AsyncMock,
            return_value={
                "weather_max_temp_today": 25,
                "weather_min_temp_today": 15,
            },
        ),
    ):
        entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_WITH_NIGHT_SENSORS)
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        coordinator = entry.runtime_data.coordinator
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert coordinator.data[DATA_CLIMATE_MODE] == "summer"

    # First transition summer -> off
    hass.states.async_set("sensor.summer_night_temp", "15.0")
    await hass.async_block_till_done()
    mock_night = datetime(2026, 4, 24, 20, 0, 0, tzinfo=dt_util.UTC)
    with (
        patch("homeassistant.util.dt.now", return_value=mock_night),
        patch(
            "custom_components.offdelay.coordinator.OffdelayDataUpdateCoordinator._update_weather_data",
            new_callable=AsyncMock,
            return_value={
                "weather_max_temp_today": 25,
                "weather_min_temp_today": 15,
            },
        ),
    ):
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert coordinator.data[DATA_CLIMATE_MODE] == "off"

    # Now off -> summer (sensor above max)
    hass.states.async_set("sensor.summer_night_temp", "25.0")
    await hass.async_block_till_done()
    with (
        patch("homeassistant.util.dt.now", return_value=mock_night),
        patch(
            "custom_components.offdelay.coordinator.OffdelayDataUpdateCoordinator._update_weather_data",
            new_callable=AsyncMock,
            return_value={
                "weather_max_temp_today": 25,
                "weather_min_temp_today": 15,
            },
        ),
    ):
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert coordinator.data[DATA_CLIMATE_MODE] == "summer"


async def test_night_mode_off_to_winter(hass: HomeAssistant):
    """Test off mode transitions to winter when sensor below min temp."""
    mock_day = datetime(2026, 4, 24, 10, 0, 0, tzinfo=dt_util.UTC)
    with (
        patch("homeassistant.util.dt.now", return_value=mock_day),
        patch(
            "custom_components.offdelay.coordinator.OffdelayDataUpdateCoordinator._update_weather_data",
            new_callable=AsyncMock,
            return_value={
                "weather_max_temp_today": 10,
                "weather_min_temp_today": 5,
            },
        ),
    ):
        entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_WITH_NIGHT_SENSORS)
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        coordinator = entry.runtime_data.coordinator
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert coordinator.data[DATA_CLIMATE_MODE] == "winter"

    # First transition winter -> off
    hass.states.async_set("sensor.winter_night_temp", "25.0")
    await hass.async_block_till_done()
    mock_night = datetime(2026, 4, 24, 20, 0, 0, tzinfo=dt_util.UTC)
    with (
        patch("homeassistant.util.dt.now", return_value=mock_night),
        patch(
            "custom_components.offdelay.coordinator.OffdelayDataUpdateCoordinator._update_weather_data",
            new_callable=AsyncMock,
            return_value={
                "weather_max_temp_today": 10,
                "weather_min_temp_today": 5,
            },
        ),
    ):
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert coordinator.data[DATA_CLIMATE_MODE] == "off"

    # Now off -> winter (sensor below min)
    hass.states.async_set("sensor.winter_night_temp", "15.0")
    await hass.async_block_till_done()
    with (
        patch("homeassistant.util.dt.now", return_value=mock_night),
        patch(
            "custom_components.offdelay.coordinator.OffdelayDataUpdateCoordinator._update_weather_data",
            new_callable=AsyncMock,
            return_value={
                "weather_max_temp_today": 10,
                "weather_min_temp_today": 5,
            },
        ),
    ):
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert coordinator.data[DATA_CLIMATE_MODE] == "winter"


async def test_night_mode_sensor_unavailable(hass: HomeAssistant):
    """Test mode stays unchanged when sensor is unavailable."""
    mock_day = datetime(2026, 4, 24, 10, 0, 0, tzinfo=dt_util.UTC)
    with (
        patch("homeassistant.util.dt.now", return_value=mock_day),
        patch(
            "custom_components.offdelay.coordinator.OffdelayDataUpdateCoordinator._update_weather_data",
            new_callable=AsyncMock,
            return_value={
                "weather_max_temp_today": 10,
                "weather_min_temp_today": 5,
            },
        ),
    ):
        entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_WITH_NIGHT_SENSORS)
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        coordinator = entry.runtime_data.coordinator
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert coordinator.data[DATA_CLIMATE_MODE] == "winter"

    # Night: sensor unavailable -> mode stays winter
    hass.states.async_set("sensor.winter_night_temp", "unavailable")
    await hass.async_block_till_done()
    mock_night = datetime(2026, 4, 24, 20, 0, 0, tzinfo=dt_util.UTC)
    with (
        patch("homeassistant.util.dt.now", return_value=mock_night),
        patch(
            "custom_components.offdelay.coordinator.OffdelayDataUpdateCoordinator._update_weather_data",
            new_callable=AsyncMock,
            return_value={
                "weather_max_temp_today": 10,
                "weather_min_temp_today": 5,
            },
        ),
    ):
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert coordinator.data[DATA_CLIMATE_MODE] == "winter"


# D. Binary Sensor State Tests


async def test_climate_binary_sensors_created(hass: HomeAssistant):
    """Test climate binary sensors are created when night sensors configured."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_WITH_NIGHT_SENSORS)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.offdelay_climate_mode_winter")
    assert hass.states.get("binary_sensor.offdelay_climate_mode_summer")
    assert hass.states.get("binary_sensor.offdelay_climate_mode_winter_summer")


async def test_climate_binary_sensors_created_without_climate_config(
    hass: HomeAssistant,
):
    """Test climate binary sensors ARE created even without night sensor config."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.offdelay_climate_mode_winter")
    assert hass.states.get("binary_sensor.offdelay_climate_mode_summer")
    assert hass.states.get("binary_sensor.offdelay_climate_mode_winter_summer")

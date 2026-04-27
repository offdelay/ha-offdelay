"""Tests for Offdelay Home binary sensor, Guest Mode, and Vacation Mode switches."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.offdelay.const import DOMAIN

from .const import MOCK_CONFIG, MOCK_CONFIG_WITH_OCCUPANCY


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


async def _setup_entry(
    hass: HomeAssistant, config: dict | None = None
) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, data=config or MOCK_CONFIG)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_home_sensor_on_when_persons_in_zone(hass: HomeAssistant):
    hass.states.async_set("zone.home", "2")
    await _setup_entry(hass)

    state = hass.states.get("binary_sensor.offdelay_is_home")
    assert state is not None
    assert state.state == STATE_ON


async def test_home_sensor_off_when_zone_empty(hass: HomeAssistant):
    hass.states.async_set("zone.home", "0")
    await _setup_entry(hass)

    state = hass.states.get("binary_sensor.offdelay_is_home")
    assert state is not None
    assert state.state == STATE_OFF


async def test_home_sensor_updates_on_zone_change(hass: HomeAssistant):
    hass.states.async_set("zone.home", "0")
    await _setup_entry(hass)

    assert hass.states.get("binary_sensor.offdelay_is_home").state == STATE_OFF

    hass.states.async_set("zone.home", "1")
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.offdelay_is_home").state == STATE_ON

    hass.states.async_set("zone.home", "0")
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.offdelay_is_home").state == STATE_OFF


async def test_guest_mode_activates_after_delay(hass: HomeAssistant):
    """Given nobody home + occupancy ON, guest mode turns ON after the configured delay."""
    hass.states.async_set("zone.home", "0")
    hass.states.async_set("binary_sensor.motion_living_room", STATE_OFF)
    await _setup_entry(hass, MOCK_CONFIG_WITH_OCCUPANCY)

    assert hass.states.get("switch.offdelay_guest_mode").state == STATE_OFF

    hass.states.async_set("binary_sensor.motion_living_room", STATE_ON)
    await hass.async_block_till_done()

    assert hass.states.get("switch.offdelay_guest_mode").state == STATE_OFF

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=5, seconds=1))
    await hass.async_block_till_done()

    assert hass.states.get("switch.offdelay_guest_mode").state == STATE_ON


async def test_guest_mode_deactivates_after_delay(hass: HomeAssistant):
    """Given guest mode ON, when occupancy clears, guest mode turns OFF after off-delay."""
    hass.states.async_set("zone.home", "0")
    hass.states.async_set("binary_sensor.motion_living_room", STATE_OFF)
    await _setup_entry(hass, MOCK_CONFIG_WITH_OCCUPANCY)

    hass.states.async_set("binary_sensor.motion_living_room", STATE_ON)
    await hass.async_block_till_done()

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=5, seconds=1))
    await hass.async_block_till_done()
    assert hass.states.get("switch.offdelay_guest_mode").state == STATE_ON

    hass.states.async_set("binary_sensor.motion_living_room", STATE_OFF)
    await hass.async_block_till_done()

    assert hass.states.get("switch.offdelay_guest_mode").state == STATE_ON

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=15, seconds=1))
    await hass.async_block_till_done()

    assert hass.states.get("switch.offdelay_guest_mode").state == STATE_OFF


async def test_guest_mode_no_activation_when_someone_home(hass: HomeAssistant):
    hass.states.async_set("zone.home", "1")
    hass.states.async_set("binary_sensor.motion_living_room", STATE_OFF)
    await _setup_entry(hass, MOCK_CONFIG_WITH_OCCUPANCY)

    hass.states.async_set("binary_sensor.motion_living_room", STATE_ON)
    await hass.async_block_till_done()

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=10))
    await hass.async_block_till_done()

    assert hass.states.get("switch.offdelay_guest_mode").state == STATE_OFF


async def test_guest_mode_turns_off_when_person_arrives(hass: HomeAssistant):
    """Given guest mode ON, when someone arrives home, guest mode immediately turns OFF."""
    hass.states.async_set("zone.home", "0")
    hass.states.async_set("binary_sensor.motion_living_room", STATE_OFF)
    await _setup_entry(hass, MOCK_CONFIG_WITH_OCCUPANCY)

    hass.states.async_set("binary_sensor.motion_living_room", STATE_ON)
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=5, seconds=1))
    await hass.async_block_till_done()
    assert hass.states.get("switch.offdelay_guest_mode").state == STATE_ON

    hass.states.async_set("zone.home", "1")
    await hass.async_block_till_done()

    assert hass.states.get("switch.offdelay_guest_mode").state == STATE_OFF


async def test_guest_mode_manual_override_persists(hass: HomeAssistant):
    """Manual ON persists through occupancy changes until next zone.home change."""
    hass.states.async_set("zone.home", "0")
    hass.states.async_set("binary_sensor.motion_living_room", STATE_OFF)
    await _setup_entry(hass, MOCK_CONFIG_WITH_OCCUPANCY)

    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.offdelay_guest_mode"}, blocking=True
    )
    assert hass.states.get("switch.offdelay_guest_mode").state == STATE_ON

    hass.states.async_set("binary_sensor.motion_living_room", STATE_ON)
    await hass.async_block_till_done()
    hass.states.async_set("binary_sensor.motion_living_room", STATE_OFF)
    await hass.async_block_till_done()

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=20))
    await hass.async_block_till_done()

    assert hass.states.get("switch.offdelay_guest_mode").state == STATE_ON

    hass.states.async_set("zone.home", "1")
    await hass.async_block_till_done()
    assert hass.states.get("switch.offdelay_guest_mode").state == STATE_OFF


async def test_vacation_mode_turns_off_after_4_hours(hass: HomeAssistant):
    """Given vacation ON >= 4h, when someone arrives home, vacation immediately turns OFF."""
    hass.states.async_set("zone.home", "0")
    await _setup_entry(hass)

    now = dt_util.utcnow()
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        await hass.services.async_call(
            "switch",
            "turn_on",
            {"entity_id": "switch.offdelay_vacation_mode"},
            blocking=True,
        )
    assert hass.states.get("switch.offdelay_vacation_mode").state == STATE_ON

    later = now + timedelta(hours=4, minutes=1)
    with patch("homeassistant.util.dt.utcnow", return_value=later):
        hass.states.async_set("zone.home", "1")
        await hass.async_block_till_done()

    assert hass.states.get("switch.offdelay_vacation_mode").state == STATE_OFF


async def test_vacation_mode_waits_until_4_hour_mark(hass: HomeAssistant):
    """Given vacation ON < 4h, when someone arrives, vacation waits until 4h mark then turns OFF."""
    hass.states.async_set("zone.home", "0")
    await _setup_entry(hass)

    now = dt_util.utcnow()
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        await hass.services.async_call(
            "switch",
            "turn_on",
            {"entity_id": "switch.offdelay_vacation_mode"},
            blocking=True,
        )

    arrival = now + timedelta(hours=2)
    with patch("homeassistant.util.dt.utcnow", return_value=arrival):
        hass.states.async_set("zone.home", "1")
        await hass.async_block_till_done()

    assert hass.states.get("switch.offdelay_vacation_mode").state == STATE_ON

    async_fire_time_changed(hass, now + timedelta(hours=4, seconds=1))
    await hass.async_block_till_done()

    assert hass.states.get("switch.offdelay_vacation_mode").state == STATE_OFF


async def test_vacation_mode_no_auto_off_when_nobody_home(hass: HomeAssistant):
    hass.states.async_set("zone.home", "0")
    await _setup_entry(hass)

    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.offdelay_vacation_mode"},
        blocking=True,
    )

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(hours=10))
    await hass.async_block_till_done()

    assert hass.states.get("switch.offdelay_vacation_mode").state == STATE_ON


async def test_vacation_mode_manual_off(hass: HomeAssistant):
    hass.states.async_set("zone.home", "0")
    await _setup_entry(hass)

    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.offdelay_vacation_mode"},
        blocking=True,
    )
    assert hass.states.get("switch.offdelay_vacation_mode").state == STATE_ON

    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.offdelay_vacation_mode"},
        blocking=True,
    )
    assert hass.states.get("switch.offdelay_vacation_mode").state == STATE_OFF

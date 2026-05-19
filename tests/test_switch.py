"""Tests for Offdelay Home binary sensor, Guest Mode, and Vacation Mode switches."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, State
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    mock_restore_cache,
)

from custom_components.offdelay.const import DOMAIN

from .const import MOCK_CONFIG, MOCK_CONFIG_WITH_OCCUPANCY, MOCK_CONFIG_WITH_PERSONS

MOCK_CONFIG_WITH_TWO_OCCUPANCY = {
    **MOCK_CONFIG_WITH_OCCUPANCY,
    "occupancy_sensors": [
        "binary_sensor.motion_living_room",
        "binary_sensor.motion_kitchen",
    ],
}


@pytest.fixture(autouse=True)
def bypass_weather():
    with patch(
        "custom_components.offdelay.coordinator.OffdelayDataUpdateCoordinator._fetch_weather_slice",
        new_callable=AsyncMock,
        return_value={
            "weather_max_temp_today": 20,
            "weather_min_temp_today": 10,
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


async def test_guest_mode_instant_on_when_two_sensors_active(hass: HomeAssistant):
    """When 2+ occupancy sensors turn ON simultaneously, guest mode activates immediately."""
    hass.states.async_set("zone.home", "0")
    hass.states.async_set("binary_sensor.motion_living_room", STATE_OFF)
    hass.states.async_set("binary_sensor.motion_kitchen", STATE_OFF)
    await _setup_entry(hass, MOCK_CONFIG_WITH_TWO_OCCUPANCY)

    assert hass.states.get("switch.offdelay_guest_mode").state == STATE_OFF

    hass.states.async_set("binary_sensor.motion_living_room", STATE_ON)
    await hass.async_block_till_done()
    # One sensor only -> ON_delay timer still applies.
    assert hass.states.get("switch.offdelay_guest_mode").state == STATE_OFF

    hass.states.async_set("binary_sensor.motion_kitchen", STATE_ON)
    await hass.async_block_till_done()
    # Second sensor flips ON -> instant activation, no timer wait.
    assert hass.states.get("switch.offdelay_guest_mode").state == STATE_ON


async def test_guest_mode_instant_on_cancels_pending_timer(hass: HomeAssistant):
    """A pending ON_delay timer is cancelled when a 2nd sensor activates."""
    hass.states.async_set("zone.home", "0")
    hass.states.async_set("binary_sensor.motion_living_room", STATE_OFF)
    hass.states.async_set("binary_sensor.motion_kitchen", STATE_OFF)
    await _setup_entry(hass, MOCK_CONFIG_WITH_TWO_OCCUPANCY)

    # Start the ON timer with one sensor.
    hass.states.async_set("binary_sensor.motion_living_room", STATE_ON)
    await hass.async_block_till_done()
    assert hass.states.get("switch.offdelay_guest_mode").state == STATE_OFF

    # Second sensor fires before the 5-minute delay -> instant ON.
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=2))
    await hass.async_block_till_done()
    hass.states.async_set("binary_sensor.motion_kitchen", STATE_ON)
    await hass.async_block_till_done()
    assert hass.states.get("switch.offdelay_guest_mode").state == STATE_ON

    # Now drop both sensors. If the old ON timer hadn't been cancelled,
    # nothing observable would change here - but turning everything off
    # must put us on the OFF_delay path, not re-trigger the ON timer.
    hass.states.async_set("binary_sensor.motion_living_room", STATE_OFF)
    hass.states.async_set("binary_sensor.motion_kitchen", STATE_OFF)
    await hass.async_block_till_done()
    assert hass.states.get("switch.offdelay_guest_mode").state == STATE_ON

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=15, seconds=1))
    await hass.async_block_till_done()
    assert hass.states.get("switch.offdelay_guest_mode").state == STATE_OFF


async def test_guest_mode_instant_on_at_startup_with_two_sensors(hass: HomeAssistant):
    """If 2+ sensors are already ON at startup with nobody home, activate immediately."""
    hass.states.async_set("zone.home", "0")
    hass.states.async_set("binary_sensor.motion_living_room", STATE_ON)
    hass.states.async_set("binary_sensor.motion_kitchen", STATE_ON)
    await _setup_entry(hass, MOCK_CONFIG_WITH_TWO_OCCUPANCY)

    assert hass.states.get("switch.offdelay_guest_mode").state == STATE_ON


async def test_guest_mode_no_auto_logic_without_occupancy_sensors(hass: HomeAssistant):
    """Without occupancy sensors configured, auto-logic is disabled.

    The switch still works as a manual toggle, but no zone/occupancy event
    can flip it - occupancy entities aren't even subscribed.
    """
    hass.states.async_set("zone.home", "0")
    await _setup_entry(hass, MOCK_CONFIG)  # no CONF_OCCUPANCY_SENSORS

    assert hass.states.get("switch.offdelay_guest_mode").state == STATE_OFF

    # Manual ON still works.
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.offdelay_guest_mode"}, blocking=True
    )
    assert hass.states.get("switch.offdelay_guest_mode").state == STATE_ON

    # Zone change must NOT auto-clear when auto-logic is disabled.
    hass.states.async_set("zone.home", "1")
    await hass.async_block_till_done()
    assert hass.states.get("switch.offdelay_guest_mode").state == STATE_ON


async def test_guest_mode_evaluates_on_startup(hass: HomeAssistant):
    """If nobody home AND occupancy already ON at startup, ON-timer must fire."""
    hass.states.async_set("zone.home", "0")
    hass.states.async_set("binary_sensor.motion_living_room", STATE_ON)

    await _setup_entry(hass, MOCK_CONFIG_WITH_OCCUPANCY)

    # ON timer started during setup; not yet elapsed.
    assert hass.states.get("switch.offdelay_guest_mode").state == STATE_OFF

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=5, seconds=1))
    await hass.async_block_till_done()

    assert hass.states.get("switch.offdelay_guest_mode").state == STATE_ON


async def test_guest_mode_restores_on_state_across_restart(hass: HomeAssistant):
    """Guest mode ON before restart is restored after restart."""
    mock_restore_cache(hass, (State("switch.offdelay_guest_mode", STATE_ON),))

    hass.states.async_set("zone.home", "0")
    hass.states.async_set("binary_sensor.motion_living_room", STATE_OFF)
    await _setup_entry(hass, MOCK_CONFIG_WITH_OCCUPANCY)

    assert hass.states.get("switch.offdelay_guest_mode").state == STATE_ON


async def test_guest_mode_restored_on_but_someone_home_clears_via_eval(
    hass: HomeAssistant,
):
    """If restored ON but someone is home at startup, evaluation clears nothing.

    Note: startup evaluation does NOT force-clear an already-ON state when
    somebody is home (no zone transition happened). Only an actual zone.home
    change clears guest mode. This test pins that intentional behavior.
    """
    mock_restore_cache(hass, (State("switch.offdelay_guest_mode", STATE_ON),))

    hass.states.async_set("zone.home", "1")
    hass.states.async_set("binary_sensor.motion_living_room", STATE_OFF)
    await _setup_entry(hass, MOCK_CONFIG_WITH_OCCUPANCY)

    # State is preserved; it will clear on the next zone.home transition.
    assert hass.states.get("switch.offdelay_guest_mode").state == STATE_ON


async def test_proximity_sensor_created(hass: HomeAssistant) -> None:
    """Given persons configured, proximity sensor is created with correct attributes."""
    hass.states.async_set("zone.home", "0")

    hass.states.async_set(
        "device_tracker.john_phone",
        "not_home",
        {"device_id": "device_123", "friendly_name": "John's Phone"},
    )
    hass.states.async_set(
        "device_tracker.jane_phone",
        "not_home",
        {"device_id": "device_456", "friendly_name": "Jane's Phone"},
    )

    hass.states.async_set(
        "person.john",
        "not_home",
        {"friendly_name": "John", "device_ids": ["device_123"]},
    )
    hass.states.async_set(
        "person.jane",
        "not_home",
        {"friendly_name": "Jane", "device_ids": ["device_456"]},
    )

    await _setup_entry(hass, MOCK_CONFIG_WITH_PERSONS)

    state = hass.states.get("sensor.home_nearest_distance")
    assert state is not None, (
        "Proximity sensor 'sensor.home_nearest_distance' was not created"
    )

    assert state.attributes.get("unit_of_measurement") == "m"
    assert state.attributes.get("friendly_name") == "home Nearest distance"

    proximity_entries = hass.config_entries.async_entries("proximity")
    assert len(proximity_entries) >= 1, "No proximity config entries were created"

    home_proximity = next(
        (entry for entry in proximity_entries if entry.data.get("zone") == "zone.home"),
        None,
    )
    assert home_proximity is not None, (
        "Proximity config entry for 'zone.home' was not created"
    )
    assert home_proximity.data["tolerance"] == 20

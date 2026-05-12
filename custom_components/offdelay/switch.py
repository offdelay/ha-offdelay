"""Switch platform for Offdelay integration.

Includes:
- Guest Mode switch
- Vacation Mode switch
- Boost switches for configured climates
"""

from __future__ import annotations

import datetime as dt
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import STATE_ON
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.event import async_call_later, async_track_state_change_event
from homeassistant.util import dt as dt_util

from .const import (
    ATTRIBUTION,
    CONF_CLIMATES_BOOST,
    CONF_GUEST_TURN_OFF_DELAY,
    CONF_GUEST_TURN_ON_DELAY,
    CONF_OCCUPANCY_SENSORS,
    DOMAIN,
)
from .entity import OffdelayEntity
from .helpers import get_climate_friendly_name

if TYPE_CHECKING:
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import OffdelayDataUpdateCoordinator
    from .data import OffdelayConfigEntry

ZONE_HOME_ENTITY = "zone.home"
VACATION_MIN_HOURS = 4


# ------------------------------------------------------------------
# Setup
# ------------------------------------------------------------------


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OffdelayConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Offdelay switches from a config entry."""
    config = dict(entry.data)
    entities: list[SwitchEntity] = []

    # Guest & Vacation modes
    entities.extend(
        [
            GuestModeSwitch(entry, config),
            VacationModeSwitch(entry),
        ]
    )

    # Boost switches (per climate)
    boost_climates = entry.data.get(CONF_CLIMATES_BOOST, [])
    coordinator = entry.runtime_data.coordinator

    for climate_id in boost_climates:
        friendly_name = get_climate_friendly_name(hass, climate_id)
        description = SwitchEntityDescription(
            key=f"boost_{climate_id.split('.')[-1]}",
            name=f"{friendly_name} Boost",
            icon="mdi:heat-wave",
        )
        entities.append(
            OffdelayBoostSwitch(
                coordinator=coordinator,
                entity_description=description,
                climate_entity_id=climate_id,
            )
        )

    async_add_entities(entities)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _device_info(entry_id: str) -> DeviceInfo:
    return DeviceInfo(
        name="Offdelay",
        identifiers={(DOMAIN, entry_id)},
        manufacturer="Offdelay",
        model="Logic Engine",
        entry_type=DeviceEntryType.SERVICE,
    )


def _zone_home_person_count(hass: HomeAssistant) -> int:
    state = hass.states.get(ZONE_HOME_ENTITY)
    if state is None:
        return 0
    try:
        return int(state.state)
    except (ValueError, TypeError):
        return 0


def _any_occupancy_on(hass: HomeAssistant, entity_ids: list[str]) -> bool:
    return any(
        (state := hass.states.get(eid)) is not None and state.state == STATE_ON
        for eid in entity_ids
    )


# ------------------------------------------------------------------
# Guest Mode
# ------------------------------------------------------------------


class GuestModeSwitch(SwitchEntity):
    """Guest mode: auto-ON when nobody home + occupancy detected."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True
    _attr_translation_key = "guest_mode"
    _attr_icon = "mdi:account-question"

    def __init__(
        self, config_entry: OffdelayConfigEntry, config: dict[str, Any]
    ) -> None:
        """Initialize guest mode switch with config entry and settings."""
        self._attr_unique_id = f"{config_entry.entry_id}_guest_mode"
        self._attr_device_info = _device_info(config_entry.entry_id)

        self._occupancy_sensors = list(config.get(CONF_OCCUPANCY_SENSORS, []))
        self._on_delay_minutes = int(config.get(CONF_GUEST_TURN_ON_DELAY, 5))
        self._off_delay_minutes = int(config.get(CONF_GUEST_TURN_OFF_DELAY, 15))

        self._is_on = False
        self._manual_override = False
        self._on_timer: CALLBACK_TYPE | None = None
        self._off_timer: CALLBACK_TYPE | None = None

    @property
    def is_on(self) -> bool:
        """Return True when guest mode is active."""
        return self._is_on

    async def async_turn_on(self, **_: object) -> None:
        """Turn guest mode on and cancel all timers."""
        self._cancel_all_timers()
        self._manual_override = True
        self._is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **_: object) -> None:
        """Turn guest mode off and cancel all timers."""
        self._cancel_all_timers()
        self._manual_override = True
        self._is_on = False
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Subscribe to zone.home and occupancy sensor changes."""
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, ZONE_HOME_ENTITY, self._async_zone_home_changed
            )
        )
        for eid in self._occupancy_sensors:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, eid, self._async_occupancy_changed
                )
            )

    async def async_will_remove_from_hass(self) -> None:
        """Cancel timers when entity is removed."""
        self._cancel_all_timers()

    @callback
    def _async_zone_home_changed(self, _event: Event) -> None:
        self._manual_override = False
        if _zone_home_person_count(self.hass) > 0:
            self._cancel_all_timers()
            if self._is_on:
                self._is_on = False
                self.async_write_ha_state()
        else:
            self._evaluate()

    @callback
    def _async_occupancy_changed(self, _event: Event) -> None:
        if not self._manual_override:
            self._evaluate()

    @callback
    def _evaluate(self) -> None:
        if _zone_home_person_count(self.hass) > 0:
            return

        occupancy = _any_occupancy_on(self.hass, self._occupancy_sensors)

        if occupancy and not self._is_on:
            self._cancel_off()
            if self._on_timer is None:
                self._on_timer = async_call_later(
                    self.hass,
                    self._on_delay_minutes * 60,
                    self._activate,
                )

        elif not occupancy and self._is_on:
            self._cancel_on()
            if self._off_timer is None:
                self._off_timer = async_call_later(
                    self.hass,
                    self._off_delay_minutes * 60,
                    self._deactivate,
                )
        else:
            self._cancel_on()

    @callback
    def _activate(self, _now: dt.datetime) -> None:
        self._on_timer = None
        if not self._manual_override:
            self._is_on = True
            self.async_write_ha_state()

    @callback
    def _deactivate(self, _now: dt.datetime) -> None:
        self._off_timer = None
        if not self._manual_override:
            self._is_on = False
            self.async_write_ha_state()

    def _cancel_on(self) -> None:
        if self._on_timer:
            self._on_timer()
            self._on_timer = None

    def _cancel_off(self) -> None:
        if self._off_timer:
            self._off_timer()
            self._off_timer = None

    def _cancel_all_timers(self) -> None:
        self._cancel_on()
        self._cancel_off()


# ------------------------------------------------------------------
# Vacation Mode
# ------------------------------------------------------------------


class VacationModeSwitch(SwitchEntity):
    """Vacation mode: auto-OFF after arrival home, min 4h."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True
    _attr_translation_key = "vacation_mode"
    _attr_icon = "mdi:beach"

    def __init__(self, config_entry: OffdelayConfigEntry) -> None:
        """Initialize vacation mode switch with config entry."""
        self._attr_unique_id = f"{config_entry.entry_id}_vacation_mode"
        self._attr_device_info = _device_info(config_entry.entry_id)

        self._is_on = False
        self._on_since: dt.datetime | None = None
        self._manual_override = False
        self._timer: CALLBACK_TYPE | None = None

    @property
    def is_on(self) -> bool:
        """Return True when vacation mode is active."""
        return self._is_on

    async def async_turn_on(self, **_: object) -> None:
        """Turn vacation mode on and record start time."""
        self._cancel()
        self._manual_override = True
        self._is_on = True
        self._on_since = dt_util.utcnow()
        self.async_write_ha_state()

    async def async_turn_off(self, **_: object) -> None:
        """Turn vacation mode off and clear timers."""
        self._cancel()
        self._manual_override = True
        self._is_on = False
        self._on_since = None
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Subscribe to zone.home state changes."""
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, ZONE_HOME_ENTITY, self._zone_changed
            )
        )

    async def async_will_remove_from_hass(self) -> None:
        """Cancel timers when entity is removed."""
        self._cancel()

    @callback
    def _zone_changed(self, _event: Event) -> None:
        self._manual_override = False
        if not self._is_on or _zone_home_person_count(self.hass) == 0:
            return

        elapsed = dt_util.utcnow() - (self._on_since or dt_util.utcnow())
        remaining = timedelta(hours=VACATION_MIN_HOURS) - elapsed

        if remaining <= timedelta(0):
            self._turn_off()
        elif self._timer is None:
            self._timer = async_call_later(
                self.hass,
                remaining.total_seconds(),
                self._async_turn_off_callback,
            )

    @callback
    def _async_turn_off_callback(self, _now: dt.datetime) -> None:
        self._timer = None
        self._turn_off()

    @callback
    def _turn_off(self) -> None:
        self._is_on = False
        self._on_since = None
        self.async_write_ha_state()

    def _cancel(self) -> None:
        if self._timer:
            self._timer()
            self._timer = None


# ------------------------------------------------------------------
# Boost Switch
# ------------------------------------------------------------------


class OffdelayBoostSwitch(OffdelayEntity, SwitchEntity):
    """Switch to control heatpump boost mode."""

    def __init__(
        self,
        coordinator: OffdelayDataUpdateCoordinator,
        entity_description: SwitchEntityDescription,
        climate_entity_id: str,
    ) -> None:
        """Initialize boost switch for a climate entity."""
        super().__init__(coordinator, entity_description)
        self._climate_entity_id = climate_entity_id
        climate_object_id = climate_entity_id.rsplit(".", maxsplit=1)[-1]
        self.entity_id = f"switch.{climate_object_id}_boost"

    @property
    def is_on(self) -> bool:
        """Return True when boost is active for this climate."""
        boost_state = self.coordinator.data.get("boost_state", {})
        return boost_state.get(self._climate_entity_id, False)

    async def async_turn_on(self, **_: object) -> None:
        """Activate boost mode for this climate entity."""
        self.coordinator.set_boost_active(self._climate_entity_id, active=True)

    async def async_turn_off(self, **_: object) -> None:
        """Deactivate boost mode for this climate entity."""
        self.coordinator.set_boost_active(self._climate_entity_id, active=False)

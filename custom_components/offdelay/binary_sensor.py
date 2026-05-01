"""Binary sensor platform for Offdelay."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    ATTRIBUTION,
    CONF_BOOST_SUMMER_TEMP,
    CONF_BOOST_WINTER_TEMP,
    CONF_CLIMATES_BOOST,
    DATA_CLIMATE_MODE,
    DOMAIN,
)
from .entity import OffdelayEntity
from .helpers import get_climate_friendly_name

if TYPE_CHECKING:
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import OffdelayDataUpdateCoordinator
    from .data import OffdelayConfigEntry


# ------------------------------------------------------------------
# Descriptions
# ------------------------------------------------------------------

ENTITY_DESCRIPTIONS = (
    BinarySensorEntityDescription(
        key="climate_mode_winter",
        translation_key="climate_mode_winter",
        icon="mdi:snowflake",
    ),
    BinarySensorEntityDescription(
        key="climate_mode_summer",
        translation_key="climate_mode_summer",
        icon="mdi:white-balance-sunny",
    ),
    BinarySensorEntityDescription(
        key="climate_mode_winter_summer",
        translation_key="climate_mode_winter_summer",
        icon="mdi:sun-snowflake-variant",
    ),
)

ZONE_HOME_ENTITY = "zone.home"


# ------------------------------------------------------------------
# Setup
# ------------------------------------------------------------------


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OffdelayConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors for Offdelay."""
    coordinator: OffdelayDataUpdateCoordinator = entry.runtime_data.coordinator

    entities: list[BinarySensorEntity] = []

    # Climate mode sensors
    entities.extend(
        OffdelayClimateModeBinarySensor(
            coordinator=coordinator,
            entity_description=description,
        )
        for description in ENTITY_DESCRIPTIONS
    )

    # Boost binary sensors (summer / winter per climate)
    boost_climates = entry.data.get(CONF_CLIMATES_BOOST, [])
    boost_summer_temp = entry.data.get(CONF_BOOST_SUMMER_TEMP, 17.0)
    boost_winter_temp = entry.data.get(CONF_BOOST_WINTER_TEMP, 24.0)
    for climate_id in boost_climates:
        friendly_name = get_climate_friendly_name(hass, climate_id)
        climate_name = climate_id.split(".")[-1]

        for boost_type, temp_label in (
            ("summer", str(boost_summer_temp)),
            ("winter", str(boost_winter_temp)),
        ):
            description = BinarySensorEntityDescription(
                key=f"boost_{climate_name}_{boost_type}",
                name=f"{friendly_name} Boost {temp_label}",
                icon="mdi:snowflake" if boost_type == "summer" else "mdi:fire",
            )

            entities.append(
                OffdelayBoostBinarySensor(
                    coordinator=coordinator,
                    entity_description=description,
                    climate_entity_id=climate_id,
                    boost_type=boost_type,
                )
            )

    # Zone.home presence sensor
    entities.append(OffdelayHomeBinarySensor(entry))

    async_add_entities(entities)


# ------------------------------------------------------------------
# Climate Mode Sensors
# ------------------------------------------------------------------


class OffdelayClimateModeBinarySensor(OffdelayEntity, BinarySensorEntity):
    """Binary sensor representing climate mode state."""

    @property
    def is_on(self) -> bool:
        key = self.entity_description.key
        mode = self.coordinator.data.get(DATA_CLIMATE_MODE)

        if key == "climate_mode_winter":
            return mode == "winter"
        if key == "climate_mode_summer":
            return mode == "summer"
        if key == "climate_mode_winter_summer":
            return mode in {"winter", "summer"}

        return False


# ------------------------------------------------------------------
# Boost Sensors
# ------------------------------------------------------------------


class OffdelayBoostBinarySensor(OffdelayEntity, BinarySensorEntity):
    """Binary sensor for heatpump boost activation (season-specific)."""

    def __init__(
        self,
        coordinator: OffdelayDataUpdateCoordinator,
        entity_description: BinarySensorEntityDescription,
        climate_entity_id: str,
        boost_type: str,
    ) -> None:
        super().__init__(coordinator, entity_description)
        self._climate_entity_id = climate_entity_id
        self._boost_type = boost_type
        climate_object_id = climate_entity_id.rsplit(".", maxsplit=1)[-1]
        self.entity_id = f"binary_sensor.{climate_object_id}_boost_{boost_type}"

    @property
    def is_on(self) -> bool:
        boost_state = self.coordinator.data.get("boost_state", {})
        switch_on = boost_state.get(self._climate_entity_id, False)

        if not switch_on:
            return False

        summer_mode = self.coordinator.data.get(DATA_CLIMATE_MODE) == "summer"

        if self._boost_type == "summer":
            return summer_mode

        return not summer_mode


# ------------------------------------------------------------------
# Presence Sensor
# ------------------------------------------------------------------


class OffdelayHomeBinarySensor(BinarySensorEntity):
    """Binary sensor: ON when at least one person is in zone.home."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True
    _attr_translation_key = "is_home"
    _attr_device_class = BinarySensorDeviceClass.PRESENCE
    _attr_icon = "mdi:home-account"

    def __init__(self, config_entry: OffdelayConfigEntry) -> None:
        self._attr_unique_id = f"{config_entry.entry_id}_is_home"
        self._attr_device_info = DeviceInfo(
            name="Offdelay",
            identifiers={(DOMAIN, config_entry.entry_id)},
            manufacturer="Offdelay",
            model="Logic Engine",
            entry_type=DeviceEntryType.SERVICE,
        )
        self._is_on = False
        self._unsub: callback | None = None

    @property
    def is_on(self) -> bool:
        return self._is_on

    async def async_added_to_hass(self) -> None:
        self._update_from_zone_state()
        self._unsub = async_track_state_change_event(
            self.hass, ZONE_HOME_ENTITY, self._async_zone_home_changed
        )

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub is not None:
            self._unsub()
            self._unsub = None

    @callback
    def _async_zone_home_changed(self, event: Event) -> None:  # noqa: ARG002
        self._update_from_zone_state()
        self.async_write_ha_state()

    def _update_from_zone_state(self) -> None:
        state = self.hass.states.get(ZONE_HOME_ENTITY)
        try:
            self._is_on = state is not None and int(state.state) > 0
        except (ValueError, TypeError):
            self._is_on = False

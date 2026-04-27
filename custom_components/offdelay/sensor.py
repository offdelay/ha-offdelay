"""Sensor platform for offdelay."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import UnitOfTemperature

from .const import CONF_CLIMATES, DATA_CLIMATE_DELTA_TO_TARGET
from .entity import OffdelayEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .data import OffdelayConfigEntry

ENTITY_DESCRIPTIONS = (
    SensorEntityDescription(
        key="weather_max_temp_today",
        translation_key="weather_max_temp_today",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="weather_min_temp_today",
        translation_key="weather_min_temp_today",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="weather_max_temp_tomorrow",
        translation_key="weather_max_temp_tomorrow",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="weather_min_temp_tomorrow",
        translation_key="weather_min_temp_tomorrow",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
)

CLIMATE_ENTITY_DESCRIPTIONS = (
    SensorEntityDescription(
        key=DATA_CLIMATE_DELTA_TO_TARGET,
        translation_key="climate_delta_to_target",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon="mdi:thermometer-lines",
    ),
)


async def async_setup_entry(  # noqa: RUF029
    hass: HomeAssistant,  # noqa: ARG001 Unused function argument: `hass`
    entry: OffdelayConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    descriptions = list(ENTITY_DESCRIPTIONS)
    if entry.data.get(CONF_CLIMATES):
        descriptions.extend(CLIMATE_ENTITY_DESCRIPTIONS)
    async_add_entities(
        OffdelaySensor(
            coordinator=entry.runtime_data.coordinator,
            entity_description=entity_description,
        )
        for entity_description in descriptions
    )


class OffdelaySensor(OffdelayEntity, SensorEntity):
    """offdelay Sensor class."""

    @property
    def native_value(self) -> float | int | str | None:
        """Return the native value of the sensor."""
        return self.coordinator.data.get(self.entity_description.key)

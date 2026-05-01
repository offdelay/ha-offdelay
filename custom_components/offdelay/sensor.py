"""Sensor platform for offdelay."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import (
    RestoreSensor,
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

WEATHER_ENTITY_DESCRIPTIONS = (
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


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001 Unused function argument: `hass`
    entry: OffdelayConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator = entry.runtime_data.coordinator

    entities: list[OffdelaySensor | OffdelayWeatherSensor] = [
        OffdelayWeatherSensor(
            coordinator=coordinator,
            entity_description=desc,
        )
        for desc in WEATHER_ENTITY_DESCRIPTIONS
    ]

    if entry.data.get(CONF_CLIMATES):
        entities.extend(
            OffdelaySensor(
                coordinator=coordinator,
                entity_description=desc,
            )
            for desc in CLIMATE_ENTITY_DESCRIPTIONS
        )

    async_add_entities(entities)


class OffdelaySensor(OffdelayEntity, SensorEntity):
    """offdelay Sensor class."""

    @property
    def native_value(self) -> float | int | str | None:
        """Return the native value of the sensor."""
        return self.coordinator.data.get(self.entity_description.key)


class OffdelayWeatherSensor(OffdelayEntity, RestoreSensor):
    """Weather sensor with state restoration across HA restarts."""

    @property
    def native_value(self) -> float | int | str | None:
        """Return the native value of the sensor."""
        value = self.coordinator.data.get(self.entity_description.key)
        if value is not None:
            return value
        return self._attr_native_value

    async def async_added_to_hass(self) -> None:
        """Restore last known state before registering coordinator listener."""
        if last_sensor_data := await self.async_get_last_sensor_data():
            self._attr_native_value = last_sensor_data.native_value
        await super().async_added_to_hass()

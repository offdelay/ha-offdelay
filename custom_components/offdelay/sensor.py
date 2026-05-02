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
from homeassistant.helpers.entity import EntityCategory

from .const import CONF_SUMMER_NIGHT_TEMP_SENSOR, CONF_WINTER_NIGHT_TEMP_SENSOR
from .entity import OffdelayEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import OffdelayDataUpdateCoordinator
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

NIGHT_TEMP_SENSOR_DESCRIPTIONS = (
    SensorEntityDescription(
        key="summer_night_temp_reading",
        translation_key="summer_night_temp_reading",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon="mdi:weather-sunny",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="winter_night_temp_reading",
        translation_key="winter_night_temp_reading",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon="mdi:snowflake",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)

NIGHT_SENSOR_CONFIG_MAP = {
    "summer_night_temp_reading": CONF_SUMMER_NIGHT_TEMP_SENSOR,
    "winter_night_temp_reading": CONF_WINTER_NIGHT_TEMP_SENSOR,
}


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001 Unused function argument: `hass`
    entry: OffdelayConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator = entry.runtime_data.coordinator

    entities: list[OffdelaySensor | OffdelayWeatherSensor | OffdelayNightTempSensor] = [
        OffdelayWeatherSensor(
            coordinator=coordinator,
            entity_description=desc,
        )
        for desc in WEATHER_ENTITY_DESCRIPTIONS
    ]

    for desc in NIGHT_TEMP_SENSOR_DESCRIPTIONS:
        config_key = NIGHT_SENSOR_CONFIG_MAP[desc.key]
        source_entity_id = entry.data.get(config_key, "")
        if source_entity_id:
            entities.append(
                OffdelayNightTempSensor(
                    coordinator=coordinator,
                    entity_description=desc,
                    source_entity_id=source_entity_id,
                )
            )

    async_add_entities(entities)


class OffdelaySensor(OffdelayEntity, SensorEntity):
    """offdelay Sensor class."""

    @property
    def native_value(self) -> float | int | str | None:
        """Return the native value of the sensor."""
        return self.coordinator.data.get(self.entity_description.key)


class OffdelayNightTempSensor(OffdelayEntity, RestoreSensor):
    """Sensor that mirrors a configured night temperature sensor."""

    def __init__(
        self,
        coordinator: OffdelayDataUpdateCoordinator,
        entity_description: SensorEntityDescription,
        source_entity_id: str,
    ) -> None:
        """Initialize with source entity ID."""
        super().__init__(coordinator, entity_description)
        self._source_entity_id = source_entity_id

    @property
    def native_value(self) -> float | None:
        """Return the current temperature from the source sensor."""
        if not self._source_entity_id:
            return self._attr_native_value
        state = self.coordinator.hass.states.get(self._source_entity_id)
        if state is None or state.state in {"unavailable", "unknown"}:
            return self._attr_native_value
        try:
            return float(state.state)
        except (ValueError, TypeError):
            return self._attr_native_value

    async def async_added_to_hass(self) -> None:
        """Restore last known state before registering coordinator listener."""
        if last_sensor_data := await self.async_get_last_sensor_data():
            self._attr_native_value = last_sensor_data.native_value
        await super().async_added_to_hass()


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

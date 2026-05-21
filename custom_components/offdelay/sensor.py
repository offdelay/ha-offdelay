"""Sensor platform for offdelay."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import callback
from homeassistant.helpers.event import (
    EventStateChangedData,
    async_track_state_change_event,
)

from .const import CONF_SUMMER_NIGHT_TEMP_SENSOR, CONF_WINTER_NIGHT_TEMP_SENSOR
from .entity import OffdelayEntity
from .helpers import parse_float_state

if TYPE_CHECKING:
    from homeassistant.core import Event, HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import OffdelayDataUpdateCoordinator
    from .data import OffdelayConfigEntry

WEATHER_ENTITY_DESCRIPTIONS = (
    SensorEntityDescription(
        key="weather_max_temp_today",
        translation_key="weather_max_temp_today",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="weather_min_temp_today",
        translation_key="weather_min_temp_today",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
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

    entities: list[OffdelayWeatherSensor | OffdelayNightTempSensor] = [
        OffdelayWeatherSensor(
            coordinator=coordinator,
            entity_description=desc,
        )
        for desc in WEATHER_ENTITY_DESCRIPTIONS
    ]

    for desc in NIGHT_TEMP_SENSOR_DESCRIPTIONS:
        config_key = NIGHT_SENSOR_CONFIG_MAP[desc.key]
        source_entity_ids = entry.data.get(config_key, [])
        if source_entity_ids:
            entities.append(
                OffdelayNightTempSensor(
                    coordinator=coordinator,
                    entity_description=desc,
                    source_entity_ids=source_entity_ids,
                )
            )

    async_add_entities(entities)


class OffdelayNightTempSensor(OffdelayEntity, RestoreSensor):
    """Sensor that mirrors a configured night temperature sensor."""

    def __init__(
        self,
        coordinator: OffdelayDataUpdateCoordinator,
        entity_description: SensorEntityDescription,
        source_entity_ids: list[str],
    ) -> None:
        """Initialize with source entity IDs."""
        super().__init__(coordinator, entity_description)
        self._source_entity_ids = list(dict.fromkeys(source_entity_ids))
        # Summer night: hottest reading wins (max).
        # Winter night: coldest reading wins (min).
        self._aggregator = max if entity_description.key.startswith("summer") else min

    @property
    def native_value(self) -> float | None:
        """Return the current temperature from coordinator data or restored value."""
        value = self.coordinator.data.get(self.entity_description.key)
        if value is not None:
            return value  # type: ignore[return-value]
        return self._attr_native_value  # type: ignore[return-value]

    async def async_added_to_hass(self) -> None:
        """Restore last known state and start tracking source sensor."""
        if last_sensor_data := await self.async_get_last_sensor_data():
            self._attr_native_value = last_sensor_data.native_value
        await super().async_added_to_hass()

        self._seed_initial_state()

        if self._source_entity_ids:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass,
                    self._source_entity_ids,
                    self._handle_source_state_change,
                )
            )

    def _aggregate(self) -> float | None:
        values = []
        for eid in self._source_entity_ids:
            state = self.hass.states.get(eid)
            value = parse_float_state(state)
            if value is not None:
                values.append(value)
        return self._aggregator(values) if values else None

    def _seed_initial_state(self) -> None:
        """Read the source sensors and forward the aggregated value to the coordinator."""
        if not self._source_entity_ids:
            return
        value = self._aggregate()
        if value is None and self._attr_native_value is not None:
            value = float(self._attr_native_value)
        if value is not None:
            self.coordinator.handle_night_temp_change(
                self.entity_description.key, value
            )

    @callback
    def _handle_source_state_change(self, event: Event[EventStateChangedData]) -> None:  # noqa: ARG002
        """Handle source sensor state changes."""
        value = self._aggregate()
        if value is None:
            return
        self.coordinator.handle_night_temp_change(self.entity_description.key, value)


class OffdelayWeatherSensor(OffdelayEntity, RestoreSensor):
    """Weather sensor with state restoration across HA restarts."""

    @property
    def native_value(self) -> float | int | str | None:
        """Return the native value of the sensor."""
        value = self.coordinator.data.get(self.entity_description.key)
        if value is not None:
            return value
        return self._attr_native_value  # type: ignore

    async def async_added_to_hass(self) -> None:
        """Restore last known state before registering coordinator listener."""
        if last_sensor_data := await self.async_get_last_sensor_data():
            self._attr_native_value = last_sensor_data.native_value
        await super().async_added_to_hass()

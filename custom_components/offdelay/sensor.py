"""Sensor platform for offdelay."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import callback
from homeassistant.helpers.event import (
    EventStateChangedData,
    async_track_state_change_event,
)

from .const import (
    CONF_SUMMER_NIGHT_TEMP_SENSOR,
    CONF_WINTER_NIGHT_TEMP_SENSOR,
    EVCC_GRID_POWER_ENTITY,
    EVCC_PV_POWER_ENTITY,
)
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

ENERGY_POWER_DESCRIPTIONS = (
    SensorEntityDescription(
        key="offdelay_grid_consumption_power",
        translation_key="offdelay_grid_consumption_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="offdelay_grid_return_power",
        translation_key="offdelay_grid_return_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

ENERGY_ACCUMULATION_DESCRIPTIONS = (
    SensorEntityDescription(
        key="offdelay_grid_consumption_energy",
        translation_key="offdelay_grid_consumption_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="offdelay_grid_return_energy",
        translation_key="offdelay_grid_return_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="offdelay_solar_energy",
        translation_key="offdelay_solar_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
)

ENERGY_ACCUMULATION_SOURCE_MAP = {
    "offdelay_grid_consumption_energy": EVCC_GRID_POWER_ENTITY,
    "offdelay_grid_return_energy": EVCC_GRID_POWER_ENTITY,
    "offdelay_solar_energy": EVCC_PV_POWER_ENTITY,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OffdelayConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator = entry.runtime_data.coordinator

    entities: list[
        OffdelayWeatherSensor
        | OffdelayNightTempSensor
        | OffdelayPowerSensor
        | OffdelayEnergySensor
    ] = [
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

    grid_state = hass.states.get(EVCC_GRID_POWER_ENTITY)
    pv_state = hass.states.get(EVCC_PV_POWER_ENTITY)

    if grid_state is not None and pv_state is not None:
        entities.append(
            OffdelayPowerSensor(
                coordinator=coordinator,
                entity_description=ENERGY_POWER_DESCRIPTIONS[0],
                source_entity_id=EVCC_GRID_POWER_ENTITY,
            )
        )
        entities.append(
            OffdelayPowerSensor(
                coordinator=coordinator,
                entity_description=ENERGY_POWER_DESCRIPTIONS[1],
                source_entity_id=EVCC_GRID_POWER_ENTITY,
            )
        )

        entities.extend(
            OffdelayEnergySensor(
                coordinator=coordinator,
                entity_description=desc,
                source_entity_id=ENERGY_ACCUMULATION_SOURCE_MAP[desc.key],
            )
            for desc in ENERGY_ACCUMULATION_DESCRIPTIONS
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


class OffdelayPowerSensor(OffdelayEntity, RestoreSensor):
    """Sensor that derives consumption/return power from evcc grid power."""

    def __init__(
        self,
        coordinator: OffdelayDataUpdateCoordinator,
        entity_description: SensorEntityDescription,
        source_entity_id: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, entity_description)
        self._source_entity_id = source_entity_id

    @property
    def native_value(self) -> float | None:
        """Return power in W."""
        state = self.hass.states.get(self._source_entity_id)
        if state is None or state.state in ("unknown", "unavailable"):
            return self._attr_native_value  # type: ignore[return-value]
        try:
            raw = float(state.state)
        except (ValueError, TypeError):
            return self._attr_native_value  # type: ignore[return-value]

        if self.entity_description.key == "offdelay_grid_consumption_power":
            return raw if raw >= 0 else 0.0
        if self.entity_description.key == "offdelay_grid_return_power":
            return abs(raw) if raw < 0 else 0.0
        return raw

    async def async_added_to_hass(self) -> None:
        """Restore and start tracking."""
        if last_sensor_data := await self.async_get_last_sensor_data():
            self._attr_native_value = last_sensor_data.native_value
        await super().async_added_to_hass()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                [self._source_entity_id],
                self._handle_source_change,
            )
        )

    @callback
    def _handle_source_change(self, event: Event[EventStateChangedData]) -> None:  # noqa: ARG002
        """Handle source entity state change."""
        self.async_write_ha_state()


class OffdelayEnergySensor(OffdelayEntity, RestoreSensor):
    """Energy sensor using left Riemann sum integration of a power source."""

    def __init__(
        self,
        coordinator: OffdelayDataUpdateCoordinator,
        entity_description: SensorEntityDescription,
        source_entity_id: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, entity_description)
        self._source_entity_id = source_entity_id
        self._accumulated: float = 0.0
        self._last_update: float | None = None
        self._last_power: float | None = None

    @property
    def native_value(self) -> float | None:
        """Return accumulated energy in Wh."""
        if self._accumulated > 0:
            return round(self._accumulated, 6)
        return self._attr_native_value  # type: ignore[return-value]

    async def async_added_to_hass(self) -> None:
        """Restore accumulated value and start tracking."""
        if last_sensor_data := await self.async_get_last_sensor_data():
            try:
                self._accumulated = float(last_sensor_data.native_value or 0)
            except (ValueError, TypeError):
                self._accumulated = 0.0
        await super().async_added_to_hass()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                [self._source_entity_id],
                self._handle_source_change,
            )
        )

    def _get_effective_power(self) -> float | None:
        """Read source entity and apply consumption/return derivation."""
        state = self.hass.states.get(self._source_entity_id)
        if state is None or state.state in ("unknown", "unavailable"):
            return None
        try:
            raw = float(state.state)
        except (ValueError, TypeError):
            return None

        if self.entity_description.key == "offdelay_grid_consumption_energy":
            return raw if raw >= 0 else 0.0
        if self.entity_description.key == "offdelay_grid_return_energy":
            return abs(raw) if raw < 0 else 0.0
        return raw

    @callback
    def _handle_source_change(self, event: Event[EventStateChangedData]) -> None:  # noqa: ARG002
        """Accumulate energy on source power change."""
        now = time.monotonic()
        power = self._get_effective_power()

        if self._last_power is not None and self._last_update is not None:
            elapsed_hours = (now - self._last_update) / 3600.0
            self._accumulated += self._last_power * elapsed_hours

        if power is not None:
            self._last_power = power
            self._last_update = now
        self.async_write_ha_state()

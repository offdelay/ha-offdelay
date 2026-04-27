"""DataUpdateCoordinator for offdelay."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CLIMATE_MODE_OFF,
    CLIMATE_MODE_SUMMER,
    CLIMATE_MODE_WINTER,
    CONF_CLIMATE_DAY_START_HOUR,
    CONF_CLIMATE_DELTA_TOLERANCE,
    CONF_CLIMATE_NIGHT_START_HOUR,
    CONF_CLIMATES,
    CONF_SUMMER_MIN_TEMP,
    CONF_WINTER_MAX_TEMP,
    DATA_CLIMATE_DELTA_TO_TARGET,
    DATA_CLIMATE_MODE,
    LOGGER,
)
from .data import OffdelayConfigEntry


class OffdelayDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to manage fetching API data, weather, and home status."""

    config_entry: OffdelayConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: OffdelayConfigEntry) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass, LOGGER, name="Offdelay Coordinator", update_interval=None
        )

        self.config_entry = config_entry

        self.data: dict[str, Any] = {}
        self.boost_state: dict[str, bool] = {}  # climate entity_id -> boost active

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch all coordinator data."""
        data: dict[str, Any] = {}

        weather = await self._update_weather_data()

        if weather:
            data.update(weather)

        climate_deltas = self._update_climate_data()
        data.update(climate_deltas)
        climate_mode = self._update_climate_mode(data)
        data.update(climate_mode)
        data["boost_state"] = self.boost_state.copy()

        return data

    def _update_climate_data(self) -> dict[str, Any]:
        """Calculate single climate delta based on current mode."""
        climates = self.config_entry.data.get(CONF_CLIMATES, [])
        if not climates:
            return {}
        # Compute per-entity delta as target - current
        deltas: list[tuple[str, float]] = []

        for entity_id in climates:
            state = self.hass.states.get(entity_id)
            if state is None:
                LOGGER.warning("Climate entity %s not found", entity_id)
                continue

            current_temp = state.attributes.get("current_temperature")
            target_temp = state.attributes.get("temperature")

            if current_temp is None or target_temp is None:
                LOGGER.warning(
                    "Climate entity %s missing temperature attributes", entity_id
                )
                continue

            delta = float(target_temp) - float(current_temp)  # delta: target - current
            deltas.append((entity_id, delta))

        # Select single delta based on mode using dedicated helper
        if not deltas:
            return {DATA_CLIMATE_DELTA_TO_TARGET: None}

        current_mode = self.data.get(DATA_CLIMATE_MODE, CLIMATE_MODE_OFF)
        selected = self._select_climate_delta_by_mode(deltas, current_mode)
        return {DATA_CLIMATE_DELTA_TO_TARGET: selected}

    def _is_day_window(self) -> bool:
        """Check if current time is in the day (weather) window.

        Day window is [day_start, night_start). During this window,
        weather-based logic determines the climate mode.
        """
        day_start = int(self.config_entry.data.get(CONF_CLIMATE_DAY_START_HOUR, 8))
        night_start = int(self.config_entry.data.get(CONF_CLIMATE_NIGHT_START_HOUR, 17))
        current_hour = dt_util.now().hour
        return day_start <= current_hour < night_start

    def _weather_mode_logic(
        self, current_data: dict[str, Any], current_mode: str
    ) -> dict[str, Any]:
        """Determine climate mode from weather forecast.

        Uses weather_max_temp_today to decide winter/summer/none.
        """
        weather_max_temp_today = current_data.get("weather_max_temp_today")
        if weather_max_temp_today is None:
            LOGGER.warning(
                "weather_max_temp_today is None, keeping current climate mode"
            )
            return {DATA_CLIMATE_MODE: current_mode}

        winter_max = self.config_entry.data.get(CONF_WINTER_MAX_TEMP, 0.0)
        summer_min = self.config_entry.data.get(CONF_SUMMER_MIN_TEMP, 0.0)

        if weather_max_temp_today < winter_max:
            mode = "winter"
        elif weather_max_temp_today > summer_min:
            mode = "summer"
        else:
            mode = "none"
        return {DATA_CLIMATE_MODE: mode}

    def _climate_mode_logic(
        self, climates: list[str], current_mode: str, current_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Determine climate mode from indoor climate entity temperatures.

        Checks if all climate entities indicate a mode switch is warranted.
        """
        tolerance = self.config_entry.data.get(CONF_CLIMATE_DELTA_TOLERANCE, 0.0)
        delta = current_data.get(DATA_CLIMATE_DELTA_TO_TARGET)

        if delta is None:
            return {DATA_CLIMATE_MODE: current_mode}

        # Normalize mode change decisions using single delta
        if current_mode == CLIMATE_MODE_WINTER:
            # Winter: delta is most negative (warmest room). If too warm → OFF
            if delta < -tolerance:
                return {DATA_CLIMATE_MODE: CLIMATE_MODE_OFF}
        elif current_mode == CLIMATE_MODE_SUMMER:
            # Summer: delta is most positive (coldest room). If too cold → OFF
            if delta > tolerance:
                return {DATA_CLIMATE_MODE: CLIMATE_MODE_OFF}
        elif current_mode == CLIMATE_MODE_OFF:
            if delta > tolerance:
                return {DATA_CLIMATE_MODE: CLIMATE_MODE_WINTER}
            if delta < -tolerance:
                return {DATA_CLIMATE_MODE: CLIMATE_MODE_SUMMER}

        return {DATA_CLIMATE_MODE: current_mode}

    def _update_climate_mode(self, current_data: dict[str, Any]) -> dict[str, Any]:
        """Determine climate mode based on time windows and data.

        Logic:
        - No climates configured: weather logic runs 24/7
        - Day window [day_start, night_start): weather logic
        - Night window [night_start, day_start): climate entity logic
        """
        climates = self.config_entry.data.get(CONF_CLIMATES, [])
        current_mode = self.data.get(DATA_CLIMATE_MODE, CLIMATE_MODE_OFF)

        # No climates: weather-based logic runs all day
        if not climates or self._is_day_window():
            return self._weather_mode_logic(current_data, current_mode)

        # Night window with climates: check indoor temps for mode switching
        return self._climate_mode_logic(climates, current_mode, current_data)

    def _select_climate_delta_by_mode(
        self, deltas: list[tuple[str, float]], mode: str
    ) -> float:
        """Select a single delta based on the current mode.

        Delta convention: delta = target - current.
        Positive = room too cold (needs heating). Negative = room too warm (needs cooling).

        - Winter (heating active): select the most negative delta (warmest room vs target).
          If abs(delta) > tolerance → room is too warm for heating → OFF.
        - Summer (cooling active): select the most positive delta (coldest room vs target).
          If delta > tolerance → room is too cold for cooling → OFF.
        - Off: select delta with largest absolute value (tie: first in list).
        """
        if not deltas:
            return 0.0

        delta_values = [d[1] for d in deltas]

        if mode == CLIMATE_MODE_WINTER:
            # Pick most negative delta (room most above target = least needing heat)
            negatives = [d for d in delta_values if d < 0]
            if negatives:
                selected = min(negatives)
            else:
                selected = 0.0
            LOGGER.debug("Winter delta selected: %s", selected)
            return selected
        if mode == CLIMATE_MODE_SUMMER:
            # Pick most positive delta (room most below target = least needing cooling)
            positives = [d for d in delta_values if d > 0]
            if positives:
                selected = max(positives)
            else:
                selected = 0.0
            LOGGER.debug("Summer delta selected: %s", selected)
            return selected
        if mode == CLIMATE_MODE_OFF:
            deltas_with_abs = [(entity, delta, abs(delta)) for entity, delta in deltas]
            deltas_with_abs.sort(key=lambda x: x[2], reverse=True)
            selected = deltas_with_abs[0][1]
            LOGGER.debug(
                "OFF delta selected: %s (from %s)", selected, deltas_with_abs[0][0]
            )
            return selected
        LOGGER.warning("Unknown mode %s, defaulting to OFF delta selection", mode)
        return self._select_climate_delta_by_mode(deltas, CLIMATE_MODE_OFF)

    def set_boost_active(self, climate_entity_id: str, active: bool) -> None:  # noqa: FBT001
        """Set boost state for a climate entity."""
        self.boost_state[climate_entity_id] = active
        self.async_set_updated_data(self.data)

    async def _update_weather_data(self) -> dict[str, Any]:
        """Get weather forecast data and compute values.

        Returns:
            dict[str, Any]: The weather data.

        Raises:
            UpdateFailed: If fetching weather data fails.

        """
        # Determine weather entity
        weather_entity: str | None = None
        if self.hass.states.get("weather.forecast_home"):
            weather_entity = "weather.forecast_home"
        elif self.hass.states.get("weather.home"):
            weather_entity = "weather.home"

        if weather_entity is None:
            raise UpdateFailed("No weather entity found")

        # Fetch daily forecast only
        daily_response: dict[str, Any] | None = await self.hass.services.async_call(
            "weather",
            "get_forecasts",
            {"entity_id": weather_entity, "type": "daily"},
            blocking=True,
            return_response=True,
        )

        daily_data: dict[str, Any] = (
            daily_response.get(weather_entity, {}) if daily_response else {}
        )
        daily_forecast: list[dict[str, Any]] = daily_data.get("forecast", [])

        # Get today's and tomorrow's data
        today_data: dict[str, Any] = (
            daily_forecast[0] if len(daily_forecast) > 0 else {}
        )
        tomorrow_data: dict[str, Any] = (
            daily_forecast[1] if len(daily_forecast) > 1 else {}
        )

        # Extract temperatures
        today_max_temp: float = (
            float(today_data.get("temperature", 17.0))
            if isinstance(today_data.get("temperature"), (int, float))
            else 17.0
        )
        today_min_temp: float = (
            float(today_data.get("templow", 7.0))
            if isinstance(today_data.get("templow"), (int, float))
            else 7.0
        )
        tomorrow_max_temp: float = (
            float(tomorrow_data.get("temperature", 17.0))
            if isinstance(tomorrow_data.get("temperature"), (int, float))
            else 17.0
        )
        tomorrow_min_temp: float = (
            float(tomorrow_data.get("templow", 7.0))
            if isinstance(tomorrow_data.get("templow"), (int, float))
            else 7.0
        )

        return {
            "weather_max_temp_today": today_max_temp,
            "weather_min_temp_today": today_min_temp,
            "weather_max_temp_tomorrow": tomorrow_max_temp,
            "weather_min_temp_tomorrow": tomorrow_min_temp,
        }

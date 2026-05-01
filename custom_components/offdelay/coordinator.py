"""DataUpdateCoordinator for offdelay."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    CLIMATE_MODE_OFF,
    CLIMATE_MODE_SUMMER,
    CLIMATE_MODE_WINTER,
    CONF_CLIMATE_DAY_START_HOUR,
    CONF_CLIMATE_NIGHT_START_HOUR,
    CONF_SUMMER_MIN_TEMP,
    CONF_SUMMER_NIGHT_MAX_TEMP,
    CONF_SUMMER_NIGHT_MIN_TEMP,
    CONF_SUMMER_NIGHT_TEMP_SENSOR,
    CONF_WINTER_MAX_TEMP,
    CONF_WINTER_NIGHT_MAX_TEMP,
    CONF_WINTER_NIGHT_MIN_TEMP,
    CONF_WINTER_NIGHT_TEMP_SENSOR,
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

        climate_mode = self._update_climate_mode(data)
        data.update(climate_mode)
        data["boost_state"] = self.boost_state.copy()

        return data

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

    def _climate_mode_logic(self, current_mode: str) -> dict[str, Any]:
        """Determine climate mode from night temperature sensors."""
        if current_mode == CLIMATE_MODE_SUMMER:
            sensor_id = self.config_entry.data.get(CONF_SUMMER_NIGHT_TEMP_SENSOR)
            if not sensor_id:
                return {DATA_CLIMATE_MODE: current_mode}
            state = self.hass.states.get(sensor_id)
            if state is None or state.state in {"unavailable", "unknown"}:
                LOGGER.warning("Summer night temp sensor %s unavailable", sensor_id)
                return {DATA_CLIMATE_MODE: current_mode}
            try:
                temp = float(state.state)
            except (ValueError, TypeError):
                LOGGER.warning(
                    "Summer night temp sensor %s has invalid state: %s",
                    sensor_id,
                    state.state,
                )
                return {DATA_CLIMATE_MODE: current_mode}
            min_temp = float(
                self.config_entry.data.get(CONF_SUMMER_NIGHT_MIN_TEMP, 20.0)
            )
            if temp < min_temp:
                return {DATA_CLIMATE_MODE: CLIMATE_MODE_OFF}
        elif current_mode == CLIMATE_MODE_WINTER:
            sensor_id = self.config_entry.data.get(CONF_WINTER_NIGHT_TEMP_SENSOR)
            if not sensor_id:
                return {DATA_CLIMATE_MODE: current_mode}
            state = self.hass.states.get(sensor_id)
            if state is None or state.state in {"unavailable", "unknown"}:
                LOGGER.warning("Winter night temp sensor %s unavailable", sensor_id)
                return {DATA_CLIMATE_MODE: current_mode}
            try:
                temp = float(state.state)
            except (ValueError, TypeError):
                LOGGER.warning(
                    "Winter night temp sensor %s has invalid state: %s",
                    sensor_id,
                    state.state,
                )
                return {DATA_CLIMATE_MODE: current_mode}
            max_temp = float(
                self.config_entry.data.get(CONF_WINTER_NIGHT_MAX_TEMP, 20.0)
            )
            if temp > max_temp:
                return {DATA_CLIMATE_MODE: CLIMATE_MODE_OFF}
        elif current_mode == CLIMATE_MODE_OFF:
            summer_sensor_id = self.config_entry.data.get(CONF_SUMMER_NIGHT_TEMP_SENSOR)
            if summer_sensor_id:
                state = self.hass.states.get(summer_sensor_id)
                if state and state.state not in {"unavailable", "unknown"}:
                    try:
                        temp = float(state.state)
                        max_temp = float(
                            self.config_entry.data.get(CONF_SUMMER_NIGHT_MAX_TEMP, 20.0)
                        )
                        if temp > max_temp:
                            return {DATA_CLIMATE_MODE: CLIMATE_MODE_SUMMER}
                    except (ValueError, TypeError):
                        pass
            winter_sensor_id = self.config_entry.data.get(CONF_WINTER_NIGHT_TEMP_SENSOR)
            if winter_sensor_id:
                state = self.hass.states.get(winter_sensor_id)
                if state and state.state not in {"unavailable", "unknown"}:
                    try:
                        temp = float(state.state)
                        min_temp = float(
                            self.config_entry.data.get(CONF_WINTER_NIGHT_MIN_TEMP, 20.0)
                        )
                        if temp < min_temp:
                            return {DATA_CLIMATE_MODE: CLIMATE_MODE_WINTER}
                    except (ValueError, TypeError):
                        pass
        return {DATA_CLIMATE_MODE: current_mode}

    def _update_climate_mode(self, current_data: dict[str, Any]) -> dict[str, Any]:
        """Determine climate mode based on time windows and data."""
        current_mode = self.data.get(DATA_CLIMATE_MODE, CLIMATE_MODE_OFF)
        has_night_sensors = bool(
            self.config_entry.data.get(CONF_SUMMER_NIGHT_TEMP_SENSOR)
            or self.config_entry.data.get(CONF_WINTER_NIGHT_TEMP_SENSOR)
        )
        if not has_night_sensors or self._is_day_window():
            return self._weather_mode_logic(current_data, current_mode)
        return self._climate_mode_logic(current_mode)

    def set_boost_active(self, climate_entity_id: str, active: bool) -> None:  # noqa: FBT001
        """Set boost state for a climate entity."""
        self.boost_state[climate_entity_id] = active
        self.async_set_updated_data(self.data)

    async def _update_weather_data(self) -> dict[str, Any]:
        """Get weather forecast data and compute values from hourly forecasts.

        Returns:
            dict[str, Any]: The weather data.

        """
        # Determine weather entity
        weather_entity: str | None = None
        if self.hass.states.get("weather.forecast_home"):
            weather_entity = "weather.forecast_home"
        elif self.hass.states.get("weather.home"):
            weather_entity = "weather.home"

        if weather_entity is None:
            LOGGER.warning(
                "No available weather entity found for Offdelay weather data"
            )
            return {}

        hourly_response: dict[str, Any] | None = await self.hass.services.async_call(
            "weather",
            "get_forecasts",
            {"entity_id": weather_entity, "type": "hourly"},
            blocking=True,
            return_response=True,
        )

        hourly_data: dict[str, Any] = (
            hourly_response.get(weather_entity, {}) if hourly_response else {}
        )
        hourly_forecast: list[dict[str, Any]] = hourly_data.get("forecast", [])

        if not hourly_forecast:
            LOGGER.warning("No hourly forecast data available")
            return {}

        today = dt_util.now().date()
        today_temps: list[float] = []

        for entry in hourly_forecast:
            entry_dt_str = entry.get("datetime")
            if entry_dt_str is None:
                continue
            entry_dt = dt_util.parse_datetime(entry_dt_str)
            if entry_dt is None:
                continue
            if entry_dt.date() == today:
                temp = entry.get("temperature")
                if isinstance(temp, (int, float)):
                    today_temps.append(float(temp))

        if not today_temps:
            LOGGER.warning("No hourly temperature data for today")
            return {}

        return {
            "weather_max_temp_today": max(today_temps),
            "weather_min_temp_today": min(today_temps),
        }

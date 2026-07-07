"""DataUpdateCoordinator for offdelay."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from typing import Any

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    CLIMATE_MODE_OFF,
    CLIMATE_MODE_SUMMER,
    CLIMATE_MODE_WINTER,
    CONF_CLIMATE_DAY_START_HOUR,
    CONF_CLIMATE_NIGHT_START_HOUR,
    CONF_CLIMATES_BOOST,
    CONF_SUMMER_DAY_MIN_TEMP,
    CONF_SUMMER_NIGHT_MAX_TEMP,
    CONF_SUMMER_NIGHT_MIN_TEMP,
    CONF_SUMMER_NIGHT_TEMP_SENSOR,
    CONF_WINTER_DAY_MAX_TEMP,
    CONF_WINTER_NIGHT_MAX_TEMP,
    CONF_WINTER_NIGHT_MIN_TEMP,
    CONF_WINTER_NIGHT_TEMP_SENSOR,
    DATA_CLIMATE_MODE,
    LOGGER,
)
from .data import OffdelayConfigEntry
from .helpers import get_evcc_mode_entity_id


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
        self._weather_retry_listeners: list[Callable[[], None]] = []

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch all coordinator data."""
        previous_mode = self.data.get(DATA_CLIMATE_MODE, CLIMATE_MODE_OFF)
        data: dict[str, Any] = {}

        for key in ("summer_night_temp_reading", "winter_night_temp_reading"):
            if (value := (self.data or {}).get(key)) is not None:
                data[key] = value

        data.update(await self._fetch_weather_slice())
        data.update(self._compute_climate_mode_slice(data))
        data["boost_state"] = self.boost_state.copy()
        self._schedule_evcc_modes_off_if_needed(
            previous_mode, data.get(DATA_CLIMATE_MODE, CLIMATE_MODE_OFF)
        )

        return data

    def _schedule_evcc_modes_off_if_needed(
        self,
        previous_mode: str,
        new_mode: str,
    ) -> None:
        """Set all tracked EVCC mode entities to off on season-mode shutdown."""
        if (
            previous_mode in {CLIMATE_MODE_SUMMER, CLIMATE_MODE_WINTER}
            and new_mode == CLIMATE_MODE_OFF
        ):
            self.hass.async_create_task(self._async_turn_off_evcc_modes())

    async def _async_turn_off_evcc_modes(self) -> None:
        """Set all discovered EVCC mode entities to off."""
        for entity_id in self._get_evcc_mode_entity_ids():
            if self.hass.states.get(entity_id) is None:
                continue

            await self.hass.services.async_call(
                "select",
                "select_option",
                {"entity_id": entity_id, "option": CLIMATE_MODE_OFF},
                blocking=True,
            )

    def _get_evcc_mode_entity_ids(self) -> list[str]:
        """Return EVCC mode entity IDs for configured boost climates."""
        boost_climates: list[str] = self.config_entry.data.get(CONF_CLIMATES_BOOST, [])
        return list(
            dict.fromkeys(get_evcc_mode_entity_id(cid) for cid in boost_climates)
        )

    def _is_day_window(self) -> bool:
        """Check if current time is in the day (weather) window.

        Day window is [day_start, night_start). During this window,
        weather-based logic determines the climate mode.
        """
        day_start = int(self.config_entry.data.get(CONF_CLIMATE_DAY_START_HOUR, 8))
        night_start = int(self.config_entry.data.get(CONF_CLIMATE_NIGHT_START_HOUR, 17))
        current_hour = dt_util.now().hour
        return day_start <= current_hour < night_start

    def _climate_mode_day_logic(
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

        winter_max = self.config_entry.data.get(CONF_WINTER_DAY_MAX_TEMP, 0.0)
        summer_min = self.config_entry.data.get(CONF_SUMMER_DAY_MIN_TEMP, 0.0)

        if weather_max_temp_today < winter_max:
            mode = CLIMATE_MODE_WINTER
        elif weather_max_temp_today > summer_min:
            mode = CLIMATE_MODE_SUMMER
        else:
            mode = CLIMATE_MODE_OFF
        return {DATA_CLIMATE_MODE: mode}

    def _climate_mode_night_logic(
        self, current_mode: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Determine climate mode from night temperature sensors."""
        if current_mode == CLIMATE_MODE_SUMMER:
            if not self.config_entry.data.get(CONF_SUMMER_NIGHT_TEMP_SENSOR):
                return {DATA_CLIMATE_MODE: current_mode}
            temp = data.get("summer_night_temp_reading")
            if temp is None:
                LOGGER.warning("Summer night temp reading unavailable")
                return {DATA_CLIMATE_MODE: current_mode}
            min_temp = float(
                self.config_entry.data.get(CONF_SUMMER_NIGHT_MIN_TEMP, 20.0)
            )
            if temp < min_temp:
                return {DATA_CLIMATE_MODE: CLIMATE_MODE_OFF}
        elif current_mode == CLIMATE_MODE_WINTER:
            if not self.config_entry.data.get(CONF_WINTER_NIGHT_TEMP_SENSOR):
                return {DATA_CLIMATE_MODE: current_mode}
            temp = data.get("winter_night_temp_reading")
            if temp is None:
                LOGGER.warning("Winter night temp reading unavailable")
                return {DATA_CLIMATE_MODE: current_mode}
            max_temp = float(
                self.config_entry.data.get(CONF_WINTER_NIGHT_MAX_TEMP, 20.0)
            )
            if temp > max_temp:
                return {DATA_CLIMATE_MODE: CLIMATE_MODE_OFF}
        elif current_mode == CLIMATE_MODE_OFF:
            summer_temp = data.get("summer_night_temp_reading")
            if summer_temp is not None:
                max_temp = float(
                    self.config_entry.data.get(CONF_SUMMER_NIGHT_MAX_TEMP, 20.0)
                )
                if summer_temp > max_temp:
                    return {DATA_CLIMATE_MODE: CLIMATE_MODE_SUMMER}
            winter_temp = data.get("winter_night_temp_reading")
            if winter_temp is not None:
                min_temp = float(
                    self.config_entry.data.get(CONF_WINTER_NIGHT_MIN_TEMP, 20.0)
                )
                if winter_temp < min_temp:
                    return {DATA_CLIMATE_MODE: CLIMATE_MODE_WINTER}
        return {DATA_CLIMATE_MODE: current_mode}

    def _compute_climate_mode_slice(
        self, current_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Determine climate mode based on time windows and data."""
        current_mode = self.data.get(DATA_CLIMATE_MODE, CLIMATE_MODE_OFF)
        weather_result = self._climate_mode_day_logic(current_data, current_mode)

        has_night_sensors = bool(
            self.config_entry.data.get(CONF_SUMMER_NIGHT_TEMP_SENSOR)
            or self.config_entry.data.get(CONF_WINTER_NIGHT_TEMP_SENSOR)
        )
        if not has_night_sensors or self._is_day_window():
            return weather_result

        weather_mode = weather_result[DATA_CLIMATE_MODE]
        return self._climate_mode_night_logic(weather_mode, current_data)

    def _update_climate_mode(self, current_data: dict[str, Any]) -> dict[str, Any]:
        """Backwards-compatible climate mode wrapper."""
        return self._compute_climate_mode_slice(current_data)

    def handle_night_temp_change(self, key: str, value: float | None) -> None:
        """Forward a night-temp source change. Recomputes climate_mode only."""
        if self.data is None:
            self.data = {}
        previous_mode = self.data.get(DATA_CLIMATE_MODE, CLIMATE_MODE_OFF)
        data = dict(self.data)
        if value is None:
            data.pop(key, None)
        else:
            data[key] = value
        data.update(self._compute_climate_mode_slice(data))
        data["boost_state"] = self.boost_state.copy()
        self._schedule_evcc_modes_off_if_needed(
            previous_mode, data.get(DATA_CLIMATE_MODE, CLIMATE_MODE_OFF)
        )
        self.async_set_updated_data(data)

    async def refresh_weather(self) -> None:
        """Explicit weather refresh; recomputes climate_mode."""
        previous_mode = self.data.get(DATA_CLIMATE_MODE, CLIMATE_MODE_OFF)
        weather = await self._fetch_weather_slice()
        data = dict(self.data or {})
        data.update(weather)
        data.update(self._compute_climate_mode_slice(data))
        data["boost_state"] = self.boost_state.copy()
        self._schedule_evcc_modes_off_if_needed(
            previous_mode, data.get(DATA_CLIMATE_MODE, CLIMATE_MODE_OFF)
        )
        self.async_set_updated_data(data)

    async def _update_weather_data(self) -> dict[str, Any]:
        """Backwards-compatible weather wrapper."""
        return await self._fetch_weather_slice()

    def set_boost_active(self, climate_entity_id: str, active: bool) -> None:  # noqa: FBT001
        """Set boost state for a climate entity."""
        self.boost_state[climate_entity_id] = active
        self.data["boost_state"] = self.boost_state.copy()
        self.async_set_updated_data(self.data)

    async def _fetch_weather_slice(self) -> dict[str, Any]:
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
            if not self._weather_retry_listeners:
                for eid in ("weather.forecast_home", "weather.home"):
                    remove = async_track_state_change_event(
                        self.hass,
                        [eid],
                        self._async_weather_entity_appeared,
                    )
                    self._weather_retry_listeners.append(remove)
                    self.config_entry.async_on_unload(remove)
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

        now = dt_util.now()
        in_24_hours = now + timedelta(hours=24)

        window_temps: list[float] = []

        for entry in hourly_forecast:
            entry_dt_str = entry.get("datetime")
            if entry_dt_str is None:
                continue

            entry_dt = dt_util.parse_datetime(entry_dt_str)
            if entry_dt is None:
                continue

            # Check if the forecast entry is within the next 24 hours
            if now <= entry_dt <= in_24_hours:
                temp = entry.get("temperature")
                if isinstance(temp, (int, float)):
                    window_temps.append(float(temp))

        if not window_temps:
            LOGGER.warning("No hourly temperature data for the next 24 hours")
            return {}

        return {
            "weather_max_temp_today": max(window_temps),
            "weather_min_temp_today": min(window_temps),
        }

    @callback
    def _async_weather_entity_appeared(self, event: Event) -> None:
        """Retry weather fetch when a tracked weather entity becomes available.

        Registered in :meth:`_fetch_weather_slice` when no weather entity
        is found during coordinator refresh. Once the entity appears,
        the listener is removed and a full weather refresh is scheduled.
        """
        new_state = event.data.get("new_state")
        if new_state is None or new_state.state in ("unknown", "unavailable"):
            return
        for remove in self._weather_retry_listeners:
            remove()
        self._weather_retry_listeners.clear()
        self.hass.async_create_task(self.refresh_weather())

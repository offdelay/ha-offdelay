"""Adds config flow for Offdelay."""

from __future__ import annotations

from typing import Any

from homeassistant import config_entries
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers import selector
import voluptuous as vol

from .const import (
    CONF_BOOST_SUMMER_TEMP,
    CONF_BOOST_WINTER_TEMP,
    CONF_CLIMATE_DAY_START_HOUR,
    CONF_CLIMATE_NIGHT_START_HOUR,
    CONF_CLIMATES_BOOST,
    CONF_GUEST_TURN_OFF_DELAY,
    CONF_GUEST_TURN_ON_DELAY,
    CONF_OCCUPANCY_SENSORS,
    CONF_PERSONS,
    CONF_SUMMER_DAY_MIN_TEMP,
    CONF_SUMMER_NIGHT_MAX_TEMP,
    CONF_SUMMER_NIGHT_MIN_TEMP,
    CONF_SUMMER_NIGHT_TEMP_SENSOR,
    CONF_WINTER_DAY_MAX_TEMP,
    CONF_WINTER_NIGHT_MAX_TEMP,
    CONF_WINTER_NIGHT_MIN_TEMP,
    CONF_WINTER_NIGHT_TEMP_SENSOR,
    DOMAIN,
)


class OffdelayFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Offdelay (Climate -> Presence -> Energy steps)."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow handler."""
        self._data: dict[str, Any] = {}

    # -------------------------------------------------------------
    # Initial setup -- Climate step
    # -------------------------------------------------------------

    async def async_step_user(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle the Climate step of the initial configuration flow."""
        return await self._async_handle_climate_step(
            user_input,
            step_id="user",
            defaults=self._data,
            description_placeholders={
                "docs_url": "https://github.com/offdelay/offdelay_integration",
            },
        )

    # -------------------------------------------------------------
    # Reconfigure -- Menu
    # -------------------------------------------------------------

    async def async_step_reconfigure(
        self,
        user_input: dict | None = None,  # noqa: ARG002
    ) -> config_entries.ConfigFlowResult:
        """Show the reconfigure menu so the user picks which group to edit."""
        self._reconfigure = True
        if not self._data:
            self._data = dict(self._get_reconfigure_entry().data)
        return self.async_show_menu(
            step_id="reconfigure",
            menu_options=[
                "reconfigure_climate",
                "reconfigure_presence",
                "reconfigure_energy",
            ],
        )

    # -------------------------------------------------------------
    # Reconfigure -- Climate group
    # -------------------------------------------------------------

    async def async_step_reconfigure_climate(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Edit only the Climate group during reconfigure."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._validate(user_input, errors)
            if not errors:
                return self._async_save_reconfigure(user_input)

        return self.async_show_form(
            step_id="reconfigure_climate",
            data_schema=self._climate_schema(user_input or self._data),
            errors=errors,
        )

    # -------------------------------------------------------------
    # Reconfigure -- Presence group
    # -------------------------------------------------------------

    async def async_step_reconfigure_presence(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Edit only the Presence group during reconfigure."""
        if user_input is not None:
            return self._async_save_reconfigure(user_input)

        return self.async_show_form(
            step_id="reconfigure_presence",
            data_schema=self._presence_schema(self._data),
        )

    # -------------------------------------------------------------
    # Reconfigure -- Energy group
    # -------------------------------------------------------------

    async def async_step_reconfigure_energy(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Edit only the Energy group during reconfigure."""
        if user_input is not None:
            return self._async_save_reconfigure(user_input)

        return self.async_show_form(
            step_id="reconfigure_energy",
            data_schema=self._energy_schema(self._data),
        )

    # -------------------------------------------------------------
    # Presence step (shared between setup and reconfigure)
    # -------------------------------------------------------------

    async def async_step_presence(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle the Presence step (guest mode, persons, occupancy)."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_energy()

        return self.async_show_form(
            step_id="presence",
            data_schema=self._presence_schema(self._data),
        )

    # -------------------------------------------------------------
    # Energy step (shared between setup and reconfigure)
    # -------------------------------------------------------------

    async def async_step_energy(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle the Energy step (boost heat pump climates) and finalize setup."""
        if user_input is not None:
            self._data.update(user_input)
            return self.async_create_entry(
                title="Offdelay",
                data=self._data,
            )

        return self.async_show_form(
            step_id="energy",
            data_schema=self._energy_schema(self._data),
        )

    # -------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------

    def _async_save_reconfigure(
        self, user_input: dict
    ) -> config_entries.ConfigFlowResult:
        """Merge the edited group into entry data and finish the reconfigure."""
        self._data.update(user_input)
        return self.async_update_reload_and_abort(
            self._get_reconfigure_entry(),
            data=self._data,
        )

    async def _async_handle_climate_step(
        self,
        user_input: dict | None,
        *,
        step_id: str,
        defaults: dict,
        description_placeholders: dict[str, str] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Show or process the Climate step (owns cross-field validation)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._validate(user_input, errors)

            if not errors:
                self._data.update(user_input)
                return await self.async_step_presence()

        return self.async_show_form(
            step_id=step_id,
            description_placeholders=description_placeholders,
            data_schema=self._climate_schema(user_input or defaults),
            errors=errors,
        )

    def _validate(self, user_input: dict, errors: dict) -> None:
        """Validate Climate step user input."""
        winter = user_input[CONF_WINTER_DAY_MAX_TEMP]
        summer = user_input[CONF_SUMMER_DAY_MIN_TEMP]

        if winter >= summer:
            errors["base"] = "winter_summer_temp_conflict"
            return

        if (summer - winter) <= 0.1:
            errors["base"] = "winter_summer_temp_too_close"
            return

        day_hour = int(user_input[CONF_CLIMATE_DAY_START_HOUR])
        night_hour = int(user_input[CONF_CLIMATE_NIGHT_START_HOUR])

        if day_hour >= night_hour:
            errors["base"] = "day_night_hour_conflict"

    def _climate_schema(self, defaults: dict | None) -> vol.Schema:
        """Return the Climate group schema."""
        defaults = defaults or {}

        return vol.Schema(
            {
                vol.Required(
                    CONF_CLIMATE_DAY_START_HOUR,
                    default=defaults.get(CONF_CLIMATE_DAY_START_HOUR, 8),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        mode="box",
                        min=0,
                        max=23,
                        step=1,
                    )
                ),
                vol.Required(
                    CONF_WINTER_DAY_MAX_TEMP,
                    default=defaults.get(CONF_WINTER_DAY_MAX_TEMP, 18.0),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        mode="box",
                        unit_of_measurement=UnitOfTemperature.CELSIUS,
                        step=0.1,
                    )
                ),
                vol.Required(
                    CONF_SUMMER_DAY_MIN_TEMP,
                    default=defaults.get(CONF_SUMMER_DAY_MIN_TEMP, 24.0),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        mode="box",
                        unit_of_measurement=UnitOfTemperature.CELSIUS,
                        step=0.1,
                    )
                ),
                vol.Required(
                    CONF_CLIMATE_NIGHT_START_HOUR,
                    default=defaults.get(CONF_CLIMATE_NIGHT_START_HOUR, 17),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        mode="box",
                        min=0,
                        max=23,
                        step=1,
                    )
                ),
                vol.Optional(
                    CONF_SUMMER_NIGHT_TEMP_SENSOR,
                    default=defaults.get(CONF_SUMMER_NIGHT_TEMP_SENSOR, ""),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor",
                        multiple=False,
                    )
                ),
                vol.Required(
                    CONF_SUMMER_NIGHT_MAX_TEMP,
                    default=defaults.get(CONF_SUMMER_NIGHT_MAX_TEMP, 25.0),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        mode="box",
                        unit_of_measurement=UnitOfTemperature.CELSIUS,
                        step=0.1,
                    )
                ),
                vol.Required(
                    CONF_SUMMER_NIGHT_MIN_TEMP,
                    default=defaults.get(CONF_SUMMER_NIGHT_MIN_TEMP, 16.0),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        mode="box",
                        unit_of_measurement=UnitOfTemperature.CELSIUS,
                        step=0.1,
                    )
                ),
                vol.Optional(
                    CONF_WINTER_NIGHT_TEMP_SENSOR,
                    default=defaults.get(CONF_WINTER_NIGHT_TEMP_SENSOR, ""),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor",
                        multiple=False,
                    )
                ),
                vol.Required(
                    CONF_WINTER_NIGHT_MAX_TEMP,
                    default=defaults.get(CONF_WINTER_NIGHT_MAX_TEMP, 22.0),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        mode="box",
                        unit_of_measurement=UnitOfTemperature.CELSIUS,
                        step=0.1,
                    )
                ),
                vol.Required(
                    CONF_WINTER_NIGHT_MIN_TEMP,
                    default=defaults.get(CONF_WINTER_NIGHT_MIN_TEMP, 19.5),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        mode="box",
                        unit_of_measurement=UnitOfTemperature.CELSIUS,
                        step=0.1,
                    )
                ),
            }
        )

    def _presence_schema(self, defaults: dict | None) -> vol.Schema:
        """Return the Presence group schema."""
        defaults = defaults or {}

        return vol.Schema(
            {
                vol.Optional(
                    CONF_OCCUPANCY_SENSORS,
                    default=defaults.get(CONF_OCCUPANCY_SENSORS, []),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="binary_sensor",
                        multiple=True,
                    )
                ),
                vol.Required(
                    CONF_GUEST_TURN_ON_DELAY,
                    default=defaults.get(CONF_GUEST_TURN_ON_DELAY, 5),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        mode="box",
                        min=0,
                        step=1,
                    )
                ),
                vol.Required(
                    CONF_GUEST_TURN_OFF_DELAY,
                    default=defaults.get(CONF_GUEST_TURN_OFF_DELAY, 15),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        mode="box",
                        min=0,
                        step=1,
                    )
                ),
                vol.Optional(
                    CONF_PERSONS,
                    default=defaults.get(CONF_PERSONS, []),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="person",
                        multiple=True,
                    )
                ),
            }
        )

    def _energy_schema(self, defaults: dict | None) -> vol.Schema:
        """Return the Energy group schema (boost climates only for now)."""
        defaults = defaults or {}

        return vol.Schema(
            {
                vol.Optional(
                    CONF_CLIMATES_BOOST,
                    default=defaults.get(CONF_CLIMATES_BOOST, []),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="climate",
                        multiple=True,
                    )
                ),
                vol.Required(
                    CONF_BOOST_SUMMER_TEMP,
                    default=defaults.get(CONF_BOOST_SUMMER_TEMP, 17.0),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        mode="box",
                        min=0,
                        max=40,
                        step=0.1,
                        unit_of_measurement=UnitOfTemperature.CELSIUS,
                    )
                ),
                vol.Required(
                    CONF_BOOST_WINTER_TEMP,
                    default=defaults.get(CONF_BOOST_WINTER_TEMP, 24.0),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        mode="box",
                        min=0,
                        max=40,
                        step=0.1,
                        unit_of_measurement=UnitOfTemperature.CELSIUS,
                    )
                ),
            }
        )

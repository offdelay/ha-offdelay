"""Adds config flow for Offdelay."""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers import selector
import voluptuous as vol

from .const import (
    CONF_CLIMATE_DAY_START_HOUR,
    CONF_CLIMATE_DELTA_TOLERANCE,
    CONF_CLIMATE_NIGHT_START_HOUR,
    CONF_CLIMATES,
    CONF_CLIMATES_BOOST,
    CONF_GUEST_TURN_OFF_DELAY,
    CONF_GUEST_TURN_ON_DELAY,
    CONF_OCCUPANCY_SENSORS,
    CONF_PERSONS,
    CONF_SUMMER_MIN_TEMP,
    CONF_WINTER_MAX_TEMP,
    DOMAIN,
)


class OffdelayFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Offdelay."""

    VERSION = 1

    # -------------------------------------------------------------
    # Initial setup
    # -------------------------------------------------------------

    async def async_step_user(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial configuration step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._validate(user_input, errors)

            if not errors:
                return self.async_create_entry(
                    title="Offdelay",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            description_placeholders={
                "docs_url": "https://github.com/offdelay/offdelay_integration",
            },
            data_schema=self._schema(user_input),
            errors=errors,
        )

    # -------------------------------------------------------------
    # Reconfigure
    # -------------------------------------------------------------

    async def async_step_reconfigure(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle reconfiguration."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            self._validate(user_input, errors)

            if not errors:
                return self.async_update_reload_and_abort(
                    entry,
                    data=user_input,
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self._schema(entry.data),
            errors=errors,
        )

    # -------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------

    def _validate(self, user_input: dict, errors: dict) -> None:
        """Validate user input."""
        winter = user_input[CONF_WINTER_MAX_TEMP]
        summer = user_input[CONF_SUMMER_MIN_TEMP]

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

    def _schema(self, defaults: dict | None) -> vol.Schema:
        """Return the configuration schema."""
        defaults = defaults or {}

        return vol.Schema(
            {
                # -------------------------------------------------
                # Climate thresholds
                # -------------------------------------------------
                vol.Required(
                    CONF_WINTER_MAX_TEMP,
                    default=defaults.get(CONF_WINTER_MAX_TEMP, 20.0),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        mode="box",
                        unit_of_measurement=UnitOfTemperature.CELSIUS,
                        step=0.1,
                    )
                ),
                vol.Required(
                    CONF_SUMMER_MIN_TEMP,
                    default=defaults.get(CONF_SUMMER_MIN_TEMP, 21.0),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        mode="box",
                        unit_of_measurement=UnitOfTemperature.CELSIUS,
                        step=0.1,
                    )
                ),
                vol.Required(
                    CONF_CLIMATE_DELTA_TOLERANCE,
                    default=defaults.get(CONF_CLIMATE_DELTA_TOLERANCE, 0.5),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        mode="box",
                        unit_of_measurement=UnitOfTemperature.CELSIUS,
                        step=0.1,
                    )
                ),
                # -------------------------------------------------
                # Climate timing
                # -------------------------------------------------
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
                # -------------------------------------------------
                # Climate entities
                # -------------------------------------------------
                vol.Optional(
                    CONF_CLIMATES,
                    default=defaults.get(CONF_CLIMATES, []),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="climate",
                        multiple=True,
                    )
                ),
                vol.Optional(
                    CONF_CLIMATES_BOOST,
                    default=defaults.get(CONF_CLIMATES_BOOST, []),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="climate",
                        multiple=True,
                    )
                ),
                # -------------------------------------------------
                # Guest mode
                # -------------------------------------------------
                vol.Optional(
                    CONF_OCCUPANCY_SENSORS,
                    default=defaults.get(CONF_OCCUPANCY_SENSORS, []),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=["binary_sensor", "sensor"],
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
                # -------------------------------------------------
                # Proximity
                # -------------------------------------------------
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

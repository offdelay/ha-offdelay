"""Tests for the Offdelay multi-step config flow."""

from homeassistant import config_entries, data_entry_flow
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.offdelay.const import (
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

CLIMATE_INPUT = {
    CONF_WINTER_MAX_TEMP: 15.0,
    CONF_SUMMER_MIN_TEMP: 20.0,
    CONF_CLIMATE_DELTA_TOLERANCE: 0.5,
    CONF_CLIMATE_DAY_START_HOUR: 8,
    CONF_CLIMATE_NIGHT_START_HOUR: 17,
    CONF_CLIMATES: ["climate.living_room"],
}

PRESENCE_INPUT = {
    CONF_OCCUPANCY_SENSORS: ["binary_sensor.motion"],
    CONF_GUEST_TURN_ON_DELAY: 5,
    CONF_GUEST_TURN_OFF_DELAY: 15,
    CONF_PERSONS: ["person.john"],
}

ENERGY_INPUT = {
    CONF_CLIMATES_BOOST: ["climate.heatpump"],
}


async def test_setup_happy_path_climate_presence_energy(hass: HomeAssistant) -> None:
    """Initial setup walks Climate -> Presence -> Energy and creates a flat entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CLIMATE_INPUT
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "presence"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], PRESENCE_INPUT
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "energy"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], ENERGY_INPUT
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "Offdelay"

    expected = {**CLIMATE_INPUT, **PRESENCE_INPUT, **ENERGY_INPUT}
    assert result["data"] == expected


@pytest.mark.parametrize(
    ("payload", "expected_error"),
    [
        (
            {**CLIMATE_INPUT, CONF_WINTER_MAX_TEMP: 25.0},
            "winter_summer_temp_conflict",
        ),
        (
            {**CLIMATE_INPUT, CONF_WINTER_MAX_TEMP: 19.95},
            "winter_summer_temp_too_close",
        ),
        (
            {
                **CLIMATE_INPUT,
                CONF_CLIMATE_DAY_START_HOUR: 18,
                CONF_CLIMATE_NIGHT_START_HOUR: 17,
            },
            "day_night_hour_conflict",
        ),
    ],
)
async def test_climate_validation_blocks_advance(
    hass: HomeAssistant, payload: dict, expected_error: str
) -> None:
    """Invalid Climate input keeps the user on the Climate step with an error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], payload)
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": expected_error}


async def test_reconfigure_shows_menu(hass: HomeAssistant) -> None:
    """Reconfigure presents a menu to choose the group to edit."""
    initial = {**CLIMATE_INPUT, **PRESENCE_INPUT, **ENERGY_INPUT}
    entry = MockConfigEntry(domain=DOMAIN, data=initial, title="Offdelay")
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] == data_entry_flow.FlowResultType.MENU
    assert result["step_id"] == "reconfigure"
    assert set(result["menu_options"]) == {
        "reconfigure_climate",
        "reconfigure_presence",
        "reconfigure_energy",
    }


async def test_reconfigure_climate_only_updates_climate_keys(
    hass: HomeAssistant,
) -> None:
    """Picking Climate updates only Climate keys; other keys stay intact."""
    initial = {**CLIMATE_INPUT, **PRESENCE_INPUT, **ENERGY_INPUT}
    entry = MockConfigEntry(domain=DOMAIN, data=initial, title="Offdelay")
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "reconfigure_climate"}
    )
    assert result["step_id"] == "reconfigure_climate"

    new_climate = {**CLIMATE_INPUT, CONF_WINTER_MAX_TEMP: 16.5}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], new_climate
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    expected = {**new_climate, **PRESENCE_INPUT, **ENERGY_INPUT}
    assert dict(entry.data) == expected


async def test_reconfigure_climate_validation_blocks_advance(
    hass: HomeAssistant,
) -> None:
    """Invalid Climate edits during reconfigure surface validation errors."""
    initial = {**CLIMATE_INPUT, **PRESENCE_INPUT, **ENERGY_INPUT}
    entry = MockConfigEntry(domain=DOMAIN, data=initial, title="Offdelay")
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "reconfigure_climate"}
    )
    bad = {**CLIMATE_INPUT, CONF_WINTER_MAX_TEMP: 25.0}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], bad)
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "reconfigure_climate"
    assert result["errors"] == {"base": "winter_summer_temp_conflict"}


async def test_reconfigure_presence_only_updates_presence_keys(
    hass: HomeAssistant,
) -> None:
    """Picking Presence updates only Presence keys; other keys stay intact."""
    initial = {**CLIMATE_INPUT, **PRESENCE_INPUT, **ENERGY_INPUT}
    entry = MockConfigEntry(domain=DOMAIN, data=initial, title="Offdelay")
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "reconfigure_presence"}
    )
    assert result["step_id"] == "reconfigure_presence"

    new_presence = {**PRESENCE_INPUT, CONF_GUEST_TURN_ON_DELAY: 9}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], new_presence
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    expected = {**CLIMATE_INPUT, **new_presence, **ENERGY_INPUT}
    assert dict(entry.data) == expected


async def test_reconfigure_energy_only_updates_energy_keys(
    hass: HomeAssistant,
) -> None:
    """Picking Energy updates only Energy keys; other keys stay intact."""
    initial = {**CLIMATE_INPUT, **PRESENCE_INPUT, **ENERGY_INPUT}
    entry = MockConfigEntry(domain=DOMAIN, data=initial, title="Offdelay")
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "reconfigure_energy"}
    )
    assert result["step_id"] == "reconfigure_energy"

    new_energy = {CONF_CLIMATES_BOOST: ["climate.new_boost"]}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], new_energy
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    expected = {**CLIMATE_INPUT, **PRESENCE_INPUT, **new_energy}
    assert dict(entry.data) == expected

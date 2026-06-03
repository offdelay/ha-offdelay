"""Test the Offdelay energy, power, and water sensors."""

from __future__ import annotations

from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.offdelay.const import DOMAIN

from .const import MOCK_CONFIG


async def _setup_entry(
    hass: HomeAssistant, config: dict | None = None
) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, data=config or MOCK_CONFIG)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _register_entity(hass: HomeAssistant, entity_id: str) -> None:
    registry = er.async_get(hass)
    platform = entity_id.split(".", maxsplit=1)[0]
    object_id = entity_id.split(".", maxsplit=1)[1]
    registry.async_get_or_create(
        domain=platform,
        platform="evcc",
        unique_id=entity_id,
        suggested_object_id=object_id,
    )


async def test_power_sensors_created_when_evcc_present(hass: HomeAssistant):
    """Installed EVCC + source entities -> consumption/return power and energy sensors."""
    _register_entity(hass, "sensor.evcc_grid_power")
    _register_entity(hass, "sensor.evcc_pv_power")
    hass.states.async_set("sensor.evcc_grid_power", "1000")
    hass.states.async_set("sensor.evcc_pv_power", "2000")

    await _setup_entry(hass)

    assert hass.states.get("sensor.offdelay_grid_consumption_power") is not None
    assert hass.states.get("sensor.offdelay_grid_return_power") is not None
    assert hass.states.get("sensor.offdelay_grid_consumption_energy") is not None
    assert hass.states.get("sensor.offdelay_grid_return_energy") is not None
    assert hass.states.get("sensor.offdelay_solar_energy") is not None


async def test_power_sensors_not_created_when_evcc_missing(hass: HomeAssistant):
    """Without registered EVCC source entities, Offdelay should not create sensors."""
    await _setup_entry(hass)

    grid_power = hass.states.get("sensor.offdelay_grid_consumption_power")
    solar_energy = hass.states.get("sensor.offdelay_solar_energy")

    assert grid_power is None
    assert solar_energy is None


async def test_power_sensors_created_when_only_grid(hass: HomeAssistant):
    """Both EVCC source entities must be registered before creating sensors."""
    _register_entity(hass, "sensor.evcc_grid_power")
    hass.states.async_set("sensor.evcc_grid_power", "1000")

    await _setup_entry(hass)

    grid_power = hass.states.get("sensor.offdelay_grid_consumption_power")
    solar_energy = hass.states.get("sensor.offdelay_solar_energy")

    assert grid_power is None
    assert solar_energy is None


async def test_consumption_power_positive(hass: HomeAssistant):
    """Positive grid (2000W) -> consumption=2000, return=0."""
    _register_entity(hass, "sensor.evcc_grid_power")
    _register_entity(hass, "sensor.evcc_pv_power")
    hass.states.async_set("sensor.evcc_grid_power", "2000")
    hass.states.async_set("sensor.evcc_pv_power", "0")

    await _setup_entry(hass)

    consumption = hass.states.get("sensor.offdelay_grid_consumption_power")
    return_power = hass.states.get("sensor.offdelay_grid_return_power")
    assert consumption is not None
    assert float(consumption.state) == 2000.0
    assert return_power is not None
    assert float(return_power.state) == 0.0


async def test_return_power_negative(hass: HomeAssistant):
    """Negative grid (-1000W) -> consumption=0, return=1000."""
    _register_entity(hass, "sensor.evcc_grid_power")
    _register_entity(hass, "sensor.evcc_pv_power")
    hass.states.async_set("sensor.evcc_grid_power", "-1000")
    hass.states.async_set("sensor.evcc_pv_power", "0")

    await _setup_entry(hass)

    consumption = hass.states.get("sensor.offdelay_grid_consumption_power")
    return_power = hass.states.get("sensor.offdelay_grid_return_power")
    assert consumption is not None
    assert float(consumption.state) == 0.0
    assert return_power is not None
    assert float(return_power.state) == 1000.0


async def test_energy_sensor_exists_after_setup(hass: HomeAssistant):
    """Energy sensors are created and start in unknown state (no time elapsed)."""
    _register_entity(hass, "sensor.evcc_grid_power")
    _register_entity(hass, "sensor.evcc_pv_power")
    hass.states.async_set("sensor.evcc_grid_power", "1000")
    hass.states.async_set("sensor.evcc_pv_power", "500")

    await _setup_entry(hass)

    energy_state = hass.states.get("sensor.offdelay_grid_consumption_energy")
    assert energy_state is not None

    solar_energy = hass.states.get("sensor.offdelay_solar_energy")
    assert solar_energy is not None


async def test_power_sensors_recover_when_evcc_entities_appear_late(
    hass: HomeAssistant,
):
    """Late-loading EVCC entities should update existing Offdelay sensors."""
    _register_entity(hass, "sensor.evcc_grid_power")
    _register_entity(hass, "sensor.evcc_pv_power")
    await _setup_entry(hass)

    assert hass.states.get("sensor.offdelay_grid_consumption_power") is not None
    assert hass.states.get("sensor.offdelay_solar_energy") is not None

    hass.states.async_set("sensor.evcc_grid_power", "750")
    hass.states.async_set("sensor.evcc_pv_power", "1200")
    await hass.async_block_till_done()

    grid_power = hass.states.get("sensor.offdelay_grid_consumption_power")
    assert grid_power is not None
    assert float(grid_power.state) == 750.0


async def test_registered_evcc_entities_without_state_still_create_sensors(
    hass: HomeAssistant,
):
    """Registered EVCC entities should create sensors before states restore."""
    _register_entity(hass, "sensor.evcc_grid_power")
    _register_entity(hass, "sensor.evcc_pv_power")

    await _setup_entry(hass)

    grid_power = hass.states.get("sensor.offdelay_grid_consumption_power")
    solar_energy = hass.states.get("sensor.offdelay_solar_energy")

    assert grid_power is not None
    assert grid_power.state == STATE_UNKNOWN
    assert solar_energy is not None
    assert solar_energy.state == STATE_UNKNOWN

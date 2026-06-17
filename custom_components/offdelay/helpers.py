"""Shared helper utilities for Offdelay integration."""

from __future__ import annotations

from homeassistant.core import HomeAssistant, State


def parse_float_state(state: State | None) -> float | None:
    """Parse a state's value as float, or None for unavailable/unknown/unparseable."""
    if state is None or state.state in {"unavailable", "unknown"}:
        return None
    try:
        return float(state.state)
    except (ValueError, TypeError):
        return None


def get_climate_friendly_name(hass: HomeAssistant, climate_entity_id: str) -> str:
    """Get friendly name for a climate entity."""
    state = hass.states.get(climate_entity_id)
    if state:
        friendly_name = state.attributes.get("friendly_name")
        if friendly_name:
            return friendly_name

    climate_name = get_entity_object_id(climate_entity_id)
    return climate_name.replace("_", " ").title()


def get_entity_object_id(entity_id: str) -> str:
    """Return the object_id portion of an entity_id."""
    return entity_id.rsplit(".", maxsplit=1)[-1]


def get_evcc_mode_entity_id(climate_entity_id: str) -> str:
    """Return the EVCC mode select entity_id for a climate entity."""
    return f"select.evcc_{get_entity_object_id(climate_entity_id)}_mode"

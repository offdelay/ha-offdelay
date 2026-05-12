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

    climate_name = climate_entity_id.rsplit(".", maxsplit=1)[-1]
    return climate_name.replace("_", " ").title()

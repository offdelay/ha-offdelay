"""Shared helper utilities for Offdelay integration."""

from __future__ import annotations

from homeassistant.core import HomeAssistant


def get_climate_friendly_name(hass: HomeAssistant, climate_entity_id: str) -> str:
    """Get friendly name for a climate entity."""
    state = hass.states.get(climate_entity_id)
    if state:
        friendly_name = state.attributes.get("friendly_name")
        if friendly_name:
            return friendly_name

    climate_name = climate_entity_id.rsplit(".", maxsplit=1)[-1]
    return climate_name.replace("_", " ").title()

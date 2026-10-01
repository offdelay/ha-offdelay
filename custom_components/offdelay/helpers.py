"""Shared helper utilities for Offdelay integration."""

from __future__ import annotations

from homeassistant.core import State


def parse_float_state(state: State | None) -> float | None:
    """Parse a state's value as float, or None for unavailable/unknown/unparseable."""
    if state is None or state.state in {"unavailable", "unknown"}:
        return None
    try:
        return float(state.state)
    except (ValueError, TypeError):
        return None

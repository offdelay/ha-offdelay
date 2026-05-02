"""Tests for the Offdelay integration."""

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.offdelay.const import DOMAIN


async def test_async_setup(hass: HomeAssistant):
    """Test the component gets setup."""
    assert await async_setup_component(hass, DOMAIN, {}) is True

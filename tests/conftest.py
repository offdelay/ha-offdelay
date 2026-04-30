"""Fixtures for the Off-delay integration tests."""

from homeassistant.core import HomeAssistant
import pytest

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations."""
    return


@pytest.fixture(autouse=True)
def mock_zone_home(hass: HomeAssistant):
    """Ensure zone.home exists for all tests."""
    hass.states.async_set(
        "zone.home",
        "zoning",
        {
            "friendly_name": "Home",
            "latitude": 51.524,
            "longitude": -0.104,
            "radius": 100,
        },
    )


@pytest.fixture(name="config")
def config_fixture():
    """Provide a default configuration for the integration."""
    return {
        "platform": "offdelay",
        "delay": 10,
    }

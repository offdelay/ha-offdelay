"""Tests for the bootstrap helpers in `custom_components.offdelay.__init__`.

Covers the three new helpers added by the home-zone-autosetup work:
- ``_ensure_zone_home``
- ``_ensure_proximity_entry``
- ``_ensure_met_entry``

Plus a regression test confirming the legacy constant names are no longer
exported from ``const``.
"""

from __future__ import annotations

from importlib import import_module
from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.zone import DATA_ZONE_STORAGE_COLLECTION
from homeassistant.core import HomeAssistant
import pytest

from custom_components.offdelay import (
    _ensure_met_entry,
    _ensure_proximity_entry,
    _ensure_zone_home,
)
from custom_components.offdelay.const import HOME_NAME, HOME_ZONE, PROXIMITY_TOLERANCE

# ---------------------------------------------------------------------------
# Constant rename regression
# ---------------------------------------------------------------------------


def test_constants_renamed() -> None:
    """T1: HOME_NAME and HOME_ZONE replace the legacy constants."""
    assert HOME_NAME == "home"
    assert HOME_ZONE == "zone.home"
    assert PROXIMITY_TOLERANCE == 20

    const_module = import_module("custom_components.offdelay.const")
    assert not hasattr(const_module, "PROXIMITY_NAME")
    assert not hasattr(const_module, "PROXIMITY_ZONE")


# ---------------------------------------------------------------------------
# _ensure_zone_home
# ---------------------------------------------------------------------------


async def test_ensure_zone_home_skips_when_state_exists(hass: HomeAssistant) -> None:
    """When ``zone.home`` already exists, no storage create call is made."""
    storage_collection = MagicMock()
    storage_collection.async_create_item = AsyncMock()
    hass.data[DATA_ZONE_STORAGE_COLLECTION] = storage_collection

    # The autouse fixture in conftest already sets zone.home.
    assert hass.states.get("zone.home") is not None

    await _ensure_zone_home(hass)

    storage_collection.async_create_item.assert_not_called()


async def test_ensure_zone_home_creates_when_missing_using_ha_coords(
    hass: HomeAssistant,
) -> None:
    """When zone is missing and HA has coords, helper creates with HA coords."""
    hass.states.async_remove("zone.home")
    hass.config.latitude = 52.0
    hass.config.longitude = 4.0

    storage_collection = MagicMock()
    storage_collection.async_create_item = AsyncMock()
    hass.data[DATA_ZONE_STORAGE_COLLECTION] = storage_collection

    await _ensure_zone_home(hass)

    storage_collection.async_create_item.assert_awaited_once()
    (call_data,) = storage_collection.async_create_item.await_args.args
    assert call_data == {
        "name": "home",
        "latitude": 52.0,
        "longitude": 4.0,
        "radius": 50,
        "icon": "mdi:home",
    }


async def test_ensure_zone_home_falls_back_to_ghent(hass: HomeAssistant) -> None:
    """When HA's coords are (0.0, 0.0), helper falls back to Ghent."""
    hass.states.async_remove("zone.home")
    hass.config.latitude = 0.0
    hass.config.longitude = 0.0

    storage_collection = MagicMock()
    storage_collection.async_create_item = AsyncMock()
    hass.data[DATA_ZONE_STORAGE_COLLECTION] = storage_collection

    await _ensure_zone_home(hass)

    storage_collection.async_create_item.assert_awaited_once()
    (call_data,) = storage_collection.async_create_item.await_args.args
    assert call_data["latitude"] == pytest.approx(51.057122734917584)
    assert call_data["longitude"] == pytest.approx(3.720729617352293)
    assert call_data["name"] == "home"
    assert call_data["radius"] == 50
    assert call_data["icon"] == "mdi:home"


async def test_ensure_zone_home_skips_when_storage_not_loaded(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """When the zone storage collection isn't registered, helper logs and returns."""
    hass.states.async_remove("zone.home")
    hass.data.pop(DATA_ZONE_STORAGE_COLLECTION, None)

    with caplog.at_level("WARNING"):
        await _ensure_zone_home(hass)

    assert "Zone component not yet loaded" in caplog.text


# ---------------------------------------------------------------------------
# _ensure_proximity_entry
# ---------------------------------------------------------------------------


async def test_ensure_proximity_skips_when_entry_exists(hass: HomeAssistant) -> None:
    """When a ``proximity`` config entry already exists, no flow is initiated."""
    hass.config_entries.async_entries = MagicMock(return_value=[MagicMock()])
    flow_init = AsyncMock()
    hass.config_entries.flow.async_init = flow_init

    await _ensure_proximity_entry(hass, ["device_tracker.phone"])

    hass.config_entries.async_entries.assert_called_once_with("proximity")
    flow_init.assert_not_called()


async def test_ensure_proximity_creates_when_absent(hass: HomeAssistant) -> None:
    """When no entry exists and trackers present, flow.async_init is called once."""
    hass.config_entries.async_entries = MagicMock(return_value=[])
    flow_init = AsyncMock()
    hass.config_entries.flow.async_init = flow_init

    await _ensure_proximity_entry(hass, ["device_tracker.phone"])

    flow_init.assert_awaited_once_with(
        "proximity",
        context={"source": "user"},
        data={
            "name": "home",
            "zone": "zone.home",
            "tracked_entities": ["device_tracker.phone"],
            "tolerance": 20,
            "ignored_zones": [],
        },
    )


async def test_ensure_proximity_skips_when_no_trackers(hass: HomeAssistant) -> None:
    """Empty tracker list -> no flow.async_init call."""
    hass.config_entries.async_entries = MagicMock(return_value=[])
    flow_init = AsyncMock()
    hass.config_entries.flow.async_init = flow_init

    await _ensure_proximity_entry(hass, [])

    flow_init.assert_not_called()


# ---------------------------------------------------------------------------
# _ensure_met_entry
# ---------------------------------------------------------------------------


async def test_ensure_met_skips_when_entry_exists(hass: HomeAssistant) -> None:
    """When a ``met`` config entry already exists, no flow is initiated."""
    hass.config_entries.async_entries = MagicMock(return_value=[MagicMock()])
    flow_init = AsyncMock()
    hass.config_entries.flow.async_init = flow_init

    await _ensure_met_entry(hass)

    hass.config_entries.async_entries.assert_called_once_with("met")
    flow_init.assert_not_called()


async def test_ensure_met_creates_with_track_home_true(hass: HomeAssistant) -> None:
    """When no entry exists, flow.async_init('met', ...) is called with track_home=True."""
    hass.config_entries.async_entries = MagicMock(return_value=[])
    flow_init = AsyncMock()
    hass.config_entries.flow.async_init = flow_init
    hass.config.latitude = 52.0
    hass.config.longitude = 4.0
    hass.config.elevation = 12

    await _ensure_met_entry(hass)

    flow_init.assert_awaited_once()
    args, kwargs = flow_init.await_args
    assert args[0] == "met"
    assert kwargs["context"] == {"source": "user"}
    data = kwargs["data"]
    assert data["track_home"] is True
    assert data["latitude"] == 52.0
    assert data["longitude"] == 4.0
    assert data["elevation"] == 12
    # name uses zone.home friendly_name (set to "Home" in conftest)
    assert data["name"] == "Home"


async def test_ensure_met_elevation_falls_back_to_zero(hass: HomeAssistant) -> None:
    """When ``hass.config.elevation`` is falsy, the helper passes 0."""
    hass.config_entries.async_entries = MagicMock(return_value=[])
    flow_init = AsyncMock()
    hass.config_entries.flow.async_init = flow_init
    hass.config.elevation = 0

    await _ensure_met_entry(hass)

    flow_init.assert_awaited_once()
    _args, kwargs = flow_init.await_args
    assert kwargs["data"]["elevation"] == 0

"""Custom integration to integrate offdelay with Home Assistant.

For more details about this integration, please refer to
https://github.com/offdelay/offdelay_integration
"""

from __future__ import annotations

from datetime import timedelta

from homeassistant.components.zone import DATA_ZONE_STORAGE_COLLECTION
from homeassistant.const import (
    CONF_ICON,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_RADIUS,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.data_entry_flow import UnknownHandler
from homeassistant.helpers import entity_registry as er
from homeassistant.loader import async_get_loaded_integration

from .blueprint import async_setup_blueprints, async_unload_blueprints
from .const import (
    CONF_CLIMATES_BOOST,
    CONF_PERSONS,
    DOMAIN,
    HOME_NAME,
    HOME_ZONE,
    LOGGER,
    PLATFORMS,
    PROXIMITY_TOLERANCE,
)
from .coordinator import OffdelayDataUpdateCoordinator
from .data import OffdelayConfigEntry, OffdelayData


# https://developers.home-assistant.io/docs/config_entries_index/#setting-up-an-entry
async def async_setup_entry(
    hass: HomeAssistant,
    entry: OffdelayConfigEntry,
) -> bool:
    """Set up this integration using the UI.

    Args:
        hass: Home Assistant instance
        entry: Config entry

    Returns:
        bool: True if setup was successful, False otherwise.

    """
    await _ensure_zone_home(hass)

    persons: list[str] = entry.data.get(CONF_PERSONS, [])
    LOGGER.info("Persons configured for proximity: %s", persons)

    if persons:
        device_trackers = _get_person_device_trackers(hass, persons)
        LOGGER.info("Found device_trackers: %s", device_trackers)

        if not device_trackers:
            LOGGER.info("No device_trackers found, using persons directly")
            device_trackers = persons

        await _ensure_proximity_entry(hass, device_trackers)

    await _ensure_met_entry(hass)

    coordinator = OffdelayDataUpdateCoordinator(hass, entry)

    # Optionally set periodic update interval
    coordinator.update_interval = timedelta(hours=1)

    # Initialize runtime data
    entry.runtime_data = OffdelayData(
        integration=async_get_loaded_integration(hass, entry.domain),
        coordinator=coordinator,
    )

    # Perform first refresh
    await coordinator.async_config_entry_first_refresh()

    _cleanup_stale_boost_entities(hass, entry)

    # Set up blueprints
    await async_setup_blueprints(hass, DOMAIN)

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


def _get_person_device_trackers(
    hass: HomeAssistant,
    persons: list[str],
) -> list[str]:
    """Get device_tracker entity IDs associated with persons.

    Args:
        hass: Home Assistant instance
        persons: List of person entity IDs

    Returns:
        List of device_tracker entity IDs

    """
    device_trackers: list[str] = []

    tracker_entities = list(hass.states.async_entity_ids("device_tracker"))

    for person_entity_id in persons:
        person_state: State | None = hass.states.get(person_entity_id)
        if person_state is None:
            continue

        person_device_ids: list[str] = person_state.attributes.get("device_ids", [])
        if not person_device_ids:
            continue

        device_id_set: set[str] = set(person_device_ids)

        for tracker_entity_id in tracker_entities:
            tracker_state: State | None = hass.states.get(tracker_entity_id)
            if tracker_state is None:
                continue

            tracker_device_id: str | None = tracker_state.attributes.get("device_id")
            if tracker_device_id and tracker_device_id in device_id_set:
                device_trackers.append(tracker_entity_id)

    seen: set[str] = set()
    unique_trackers: list[str] = []
    for dt in device_trackers:
        if dt not in seen:
            seen.add(dt)
            unique_trackers.append(dt)

    return unique_trackers


# Fallback coordinates used when Home Assistant's home location is unset (0.0, 0.0).
_FALLBACK_LATITUDE = 51.057122734917584
_FALLBACK_LONGITUDE = 3.720729617352293


def _resolve_home_coords(hass: HomeAssistant) -> tuple[float, float]:
    """Return HA home coords, falling back to Ghent if unset/zero."""
    latitude = hass.config.latitude
    longitude = hass.config.longitude
    if latitude and longitude and (latitude != 0.0 or longitude != 0.0):
        return latitude, longitude
    return _FALLBACK_LATITUDE, _FALLBACK_LONGITUDE


async def _ensure_zone_home(hass: HomeAssistant) -> None:
    """Ensure ``zone.home`` exists; auto-create it via the zone storage collection if missing.

    Args:
        hass: Home Assistant instance

    Returns:
        None

    """
    if hass.states.get(HOME_ZONE) is not None:
        return

    LOGGER.warning("zone.home not configured; auto-creating with default coordinates.")

    latitude, longitude = _resolve_home_coords(hass)

    storage_collection = hass.data.get(DATA_ZONE_STORAGE_COLLECTION)
    if storage_collection is None:
        LOGGER.warning("Zone component not yet loaded; skipping zone.home auto-create.")
        return

    zone_data = {
        CONF_NAME: HOME_NAME,
        CONF_LATITUDE: latitude,
        CONF_LONGITUDE: longitude,
        CONF_RADIUS: 50,
        CONF_ICON: "mdi:home",
    }
    await storage_collection.async_create_item(zone_data)


async def _ensure_proximity_entry(
    hass: HomeAssistant,
    device_trackers: list[str],
) -> None:
    """Ensure a ``proximity`` config entry exists for this integration.

    Skips creation if any ``proximity`` config entry already exists (domain-only match).

    Args:
        hass: Home Assistant instance
        device_trackers: List of device_tracker entity IDs to track

    Returns:
        None

    """
    if hass.config_entries.async_entries("proximity"):
        LOGGER.info("Proximity integration already configured; skipping creation.")
        return

    if not device_trackers:
        LOGGER.info("No device_trackers available; skipping proximity creation.")
        return

    LOGGER.info("Creating proximity config entry with: %s", device_trackers)
    try:
        await hass.config_entries.flow.async_init(
            "proximity",
            context={"source": "user"},
            data={
                "name": HOME_NAME,
                "zone": HOME_ZONE,
                "tracked_entities": device_trackers,
                "tolerance": PROXIMITY_TOLERANCE,
                "ignored_zones": [],
            },
        )
    except UnknownHandler:
        LOGGER.warning(
            "Proximity integration is not available; skipping auto-creation."
        )
        return
    LOGGER.info("Proximity config entry created successfully")


async def _ensure_met_entry(hass: HomeAssistant) -> None:
    """Ensure a ``met`` (Meteorologisk institutt) config entry exists.

    Skips creation if any ``met`` config entry already exists (domain-only match).
    Uses ``hass.config.elevation`` if set; falls back to ``0``. Sets
    ``track_home=True`` so Met.no follows ``zone.home``.

    Args:
        hass: Home Assistant instance

    Returns:
        None

    """
    if hass.config_entries.async_entries("met"):
        LOGGER.info("Met.no integration already configured; skipping creation.")
        return

    elevation = hass.config.elevation or 0

    zone_state: State | None = hass.states.get(HOME_ZONE)
    name = (
        zone_state.attributes.get("friendly_name", HOME_NAME)
        if zone_state
        else HOME_NAME
    )

    LOGGER.info(
        "Creating Met.no config entry (track_home=True, elevation=%s)", elevation
    )
    latitude, longitude = _resolve_home_coords(hass)
    try:
        await hass.config_entries.flow.async_init(
            "met",
            context={"source": "user"},
            data={
                "name": name,
                "latitude": latitude,
                "longitude": longitude,
                "elevation": elevation,
                "track_home": True,
            },
        )
    except UnknownHandler:
        LOGGER.warning("Met.no integration is not available; skipping auto-creation.")
        return
    LOGGER.info("Met.no config entry created successfully")


def _cleanup_stale_boost_entities(
    hass: HomeAssistant,
    entry: OffdelayConfigEntry,
) -> None:
    """Remove boost entities for climates no longer in the config."""
    registry = er.async_get(hass)
    boost_climates: list[str] = entry.data.get(CONF_CLIMATES_BOOST, [])
    active_prefixes = {
        f"{entry.entry_id}_boost_{cid.split('.')[-1]}" for cid in boost_climates
    }

    for entity_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        uid = entity_entry.unique_id
        if not uid.startswith(f"{entry.entry_id}_boost_"):
            continue
        if not any(uid.startswith(prefix) for prefix in active_prefixes):
            registry.async_remove(entity_entry.entity_id)


async def async_unload_entry(
    hass: HomeAssistant,
    entry: OffdelayConfigEntry,
) -> bool:
    """Handle removal of an entry."""
    await async_unload_blueprints(hass, DOMAIN)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(
    hass: HomeAssistant,
    entry: OffdelayConfigEntry,
) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)

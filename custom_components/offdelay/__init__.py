"""Custom integration to integrate offdelay with Home Assistant.

For more details about this integration, please refer to
https://github.com/offdelay/offdelay_integration
"""

from __future__ import annotations

from datetime import timedelta

from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.loader import async_get_loaded_integration

from .blueprint import async_setup_blueprints, async_unload_blueprints
from .const import (
    CONF_PERSONS,
    DOMAIN,
    LOGGER,
    PLATFORMS,
    PROXIMITY_NAME,
    PROXIMITY_TOLERANCE,
    PROXIMITY_ZONE,
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

    Raises:
        HomeAssistantError: If zone.home is not configured.

    """
    zone_home: State | None = hass.states.get(PROXIMITY_ZONE)
    if zone_home is None:
        msg = "zone.home is not configured. Please configure the Home zone in Home Assistant."
        raise HomeAssistantError(msg)

    persons: list[str] = entry.data.get(CONF_PERSONS, [])
    LOGGER.info("Persons configured for proximity: %s", persons)

    if persons:
        device_trackers = _get_person_device_trackers(hass, persons)
        LOGGER.info("Found device_trackers: %s", device_trackers)

        if not device_trackers:
            LOGGER.info("No device_trackers found, using persons directly")
            device_trackers = persons

        if device_trackers:
            LOGGER.info("Creating proximity config entry with: %s", device_trackers)
            await hass.config_entries.flow.async_init(
                "proximity",
                context={"source": "user"},
                data={
                    "name": PROXIMITY_NAME,
                    "zone": PROXIMITY_ZONE,
                    "tracked_entities": device_trackers,
                    "tolerance": PROXIMITY_TOLERANCE,
                    "ignored_zones": [],
                },
            )
            LOGGER.info("Proximity config entry created successfully")

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

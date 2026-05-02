"""Add Offdelay blueprints to HomeAssistant."""

from __future__ import annotations

from pathlib import Path
import shutil

from homeassistant.core import HomeAssistant

from .const import LOGGER as _LOGGER


def copy_blueprints(hass: HomeAssistant, domain: str) -> None:
    """Copy blueprints to the Home Assistant blueprints folder."""
    # Get the path to the integration's blueprints directory.
    integration_blueprint_dir = Path(__file__).parent / "blueprints"

    # Get the path to the Home Assistant blueprints directory.
    ha_blueprint_dir = Path(hass.config.path("blueprints"))

    # Check if the integration's blueprints directory exists.
    if not integration_blueprint_dir.is_dir():
        _LOGGER.debug("No blueprints found in integration directory.")
        return

    # Loop through the blueprint types (automation, script).
    for blueprint_type in ("automation", "script"):
        # Check if the blueprint type directory exists in the integration.
        source_dir = integration_blueprint_dir / blueprint_type / domain
        if not source_dir.is_dir():
            continue

        # Define the destination directory.
        destination_dir = ha_blueprint_dir / blueprint_type / domain

        # Create the destination directory if it doesn't exist.
        destination_dir.mkdir(parents=True, exist_ok=True)

        # Copy the blueprint files.
        for blueprint in source_dir.glob("*.yaml"):
            destination_file = destination_dir / blueprint.name
            # Copy the file, overwriting if it exists.
            shutil.copy2(blueprint, destination_file)
            _LOGGER.debug(
                "Copied blueprint: %s/%s/%s",
                blueprint_type,
                domain,
                blueprint.name,
            )


async def async_setup_blueprints(hass: HomeAssistant, domain: str) -> None:
    """Set up the blueprints."""
    await hass.async_add_executor_job(copy_blueprints, hass, domain)


async def async_unload_blueprints(hass: HomeAssistant, domain: str) -> None:
    """Remove the blueprints."""
    await hass.async_add_executor_job(remove_blueprints, hass, domain)


def remove_blueprints(hass: HomeAssistant, domain: str) -> None:
    """Remove blueprints from the Home Assistant blueprints folder."""
    # Get the path to the Home Assistant blueprints directory.
    ha_blueprint_dir = Path(hass.config.path("blueprints"))

    # Loop through the blueprint types (automation, script).
    for blueprint_type in ("automation", "script"):
        # Define the destination directory.
        destination_dir = ha_blueprint_dir / domain / blueprint_type

        # Check if the destination directory exists.
        if destination_dir.is_dir():
            # Remove the directory and all its contents.
            shutil.rmtree(destination_dir)
            _LOGGER.debug("Removed blueprints directory: %s", destination_dir)

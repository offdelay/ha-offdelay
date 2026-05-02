"""Base entity for Offdelay."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN
from .coordinator import OffdelayDataUpdateCoordinator

if TYPE_CHECKING:
    from homeassistant.helpers.entity import EntityDescription


class OffdelayEntity(CoordinatorEntity[OffdelayDataUpdateCoordinator]):
    """Base entity for all Offdelay entities."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: OffdelayDataUpdateCoordinator,
        entity_description: EntityDescription,
    ) -> None:
        """Initialize the base entity."""
        super().__init__(coordinator)

        self.entity_description = entity_description
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{entity_description.key}"
        )
        self._attr_device_info = DeviceInfo(
            name="Offdelay",
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            manufacturer="Offdelay",
            model="Logic Engine",
            entry_type=DeviceEntryType.SERVICE,
        )

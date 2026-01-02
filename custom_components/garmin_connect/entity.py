"""Base entity for Garmin Connect integration."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


class GarminConnectEntity(CoordinatorEntity):
    """Base entity for Garmin Connect."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, unique_id: str) -> None:
        """Initialize Garmin Connect entity."""
        super().__init__(coordinator)
        self._unique_id = unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name="Garmin Connect",
            manufacturer="Garmin",
            model="Garmin Connect",
            entry_type=None,
        )

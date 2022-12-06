"""Platform for Garmin Connect integration."""
from __future__ import annotations

import logging
import voluptuous as vol
from numbers import Number


from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ID,
    DEVICE_CLASS_TIMESTAMP,
    LENGTH_KILOMETERS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)


from .alarm_util import calculate_next_active_alarms
from .const import (
    DATA_COORDINATOR,
    DOMAIN as GARMIN_DOMAIN,
    GARMIN_ENTITY_LIST,
    GEAR,
    GEAR_ICONS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up Garmin Connect sensor based on a config entry."""
    coordinator: DataUpdateCoordinator = hass.data[GARMIN_DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]
    unique_id = entry.data[CONF_ID]

    entities = []
    for (
        sensor_type,
        (name, unit, icon, device_class, enabled_by_default),
    ) in GARMIN_ENTITY_LIST.items():

        _LOGGER.debug(
            "Registering entity: %s, %s, %s, %s, %s, %s",
            sensor_type,
            name,
            unit,
            icon,
            device_class,
            enabled_by_default,
        )
        entities.append(
            GarminConnectSensor(
                coordinator,
                unique_id,
                sensor_type,
                name,
                unit,
                icon,
                device_class,
                enabled_by_default,
            )
        )
    if "gear" in coordinator.data:
        for gear_item in coordinator.data["gear"]:
            entities.append(
                GarminConnectGearSensor(
                    coordinator,
                    unique_id,
                    gear_item[GEAR.UUID],
                    gear_item["gearTypeName"],
                    gear_item["displayName"],
                    None,
                    True,
                )
            )

    async_add_entities(entities)
    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        "set_active_gear", ENTITY_SERVICE_SCHEMA, coordinator.set_active_gear
    )


ENTITY_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): str,
        vol.Required("activity_type"): str,
        vol.Required("setting"): str,
    }
)


class GarminConnectSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Garmin Connect Sensor."""

    def __init__(
        self,
        coordinator,
        unique_id,
        sensor_type,
        name,
        unit,
        icon,
        device_class,
        enabled_default: bool = True,
    ):
        """Initialize a Garmin Connect sensor."""
        super().__init__(coordinator)

        self._unique_id = unique_id
        self._type = sensor_type
        self._device_class = device_class
        self._enabled_default = enabled_default

        self._attr_name = name
        self._attr_device_class = self._device_class
        self._attr_icon = icon
        self._attr_native_unit_of_measurement = unit
        self._attr_unique_id = f"{self._unique_id}_{self._type}"
        self._attr_state_class = SensorStateClass.TOTAL

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if not self.coordinator.data or not self.coordinator.data[self._type]:
            return None

        value = self.coordinator.data[self._type]
        if "Duration" in self._type or "Seconds" in self._type:
            value = value // 60
        elif "Mass" in self._type or self._type == "weight":
            value = value / 1000
        elif self._type == "nextAlarm":
            active_alarms = calculate_next_active_alarms(
                self.coordinator.data[self._type]
            )
            if active_alarms:
                return active_alarms[0]
            else:
                return None

        if self._device_class == DEVICE_CLASS_TIMESTAMP:
            return value

        return round(value, 2) if isinstance(value, Number) else value

    @property
    def extra_state_attributes(self):
        """Return attributes for sensor."""
        if not self.coordinator.data:
            return {}

        attributes = {
            "last_synced": self.coordinator.data["lastSyncTimestampGMT"],
        }
        if self._type == "nextAlarm":
            attributes["next_alarms"] = calculate_next_active_alarms(
                self.coordinator.data[self._type]
            )

        return attributes

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return {
            "identifiers": {(GARMIN_DOMAIN, self._unique_id)},
            "name": "Garmin Connect",
            "manufacturer": "Garmin Connect",
        }

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return self._enabled_default

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            super().available
            and self.coordinator.data
            and self._type in self.coordinator.data
        )


class GarminConnectGearSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Garmin Connect Sensor."""

    def __init__(
        self,
        coordinator,
        unique_id,
        uuid,
        sensor_type,
        name,
        device_class: None,
        enabled_default: bool = True,
    ):
        """Initialize a Garmin Connect sensor."""
        super().__init__(coordinator)

        self._unique_id = unique_id
        self._type = sensor_type
        self._uuid = uuid
        self._device_class = device_class
        self._enabled_default = enabled_default

        self._attr_name = name
        self._attr_device_class = self._device_class
        self._attr_icon = GEAR_ICONS[sensor_type]
        self._attr_native_unit_of_measurement = LENGTH_KILOMETERS
        self._attr_unique_id = f"{self._unique_id}_{self._uuid}"
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_device_class = "Gear"

    @property
    def uuid(self):
        """Return the entity uuid"""
        return self._uuid

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if not self.coordinator.data or not self.get_stats():
            return None

        value = self.get_stats()["totalDistance"]
        return round(value / 1000, 2)

    @property
    def extra_state_attributes(self):
        """Return attributes for sensor."""
        gear = self.get_gear()
        stats = self.get_stats()

        if not self.coordinator.data or not gear or not stats:
            return {}

        attributes = {
            "last_synced": self.coordinator.data["lastSyncTimestampGMT"],
            "total_activities": stats["totalActivities"],
            "create_date": stats["createDate"],
            "update_date": stats["updateDate"],
            "date_begin": gear["dateBegin"],
            "date_end": gear["dateEnd"],
            "gear_make_name": gear["gearMakeName"],
            "gear_model_name": gear["gearModelName"],
            "gear_status_name": gear["gearStatusName"],
            "custom_make_model": gear["customMakeModel"],
            "maximum_meters": gear["maximumMeters"],
        }
        return attributes

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return {
            "identifiers": {(GARMIN_DOMAIN, self._unique_id)},
            "name": "Garmin Connect",
            "manufacturer": "Garmin Connect",
        }

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return self._enabled_default

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self.coordinator.data and self.get_gear()

    def get_stats(self):
        """Get gear statistics from garmin"""
        for gear_stats_item in self.coordinator.data["gear_stats"]:
            if gear_stats_item[GEAR.UUID] == self._uuid:
                return gear_stats_item

    def get_gear(self):
        """Get gear from garmin"""
        for gear_item in self.coordinator.data["gear"]:
            if gear_item[GEAR.UUID] == self._uuid:
                return gear_item

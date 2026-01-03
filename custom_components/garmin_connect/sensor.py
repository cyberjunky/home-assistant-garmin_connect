"""Platform for Garmin Connect integration."""

from __future__ import annotations

import datetime
import logging

import voluptuous as vol
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ID, UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import IntegrationError
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import (
    DOMAIN,
    GEAR_ICONS,
    Gear,
    ServiceSetting,
)
from .entity import GarminConnectEntity
from .sensor_descriptions import (
    ALL_SENSOR_DESCRIPTIONS,
)

_LOGGER = logging.getLogger(__name__)

# Limit parallel updates to prevent API rate limiting
PARALLEL_UPDATES = 1


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    """Set up Garmin Connect sensor based on a config entry."""
    coordinator: DataUpdateCoordinator = entry.runtime_data
    unique_id = entry.data[CONF_ID]

    entities = []

    # Add main sensors using entity descriptions
    for description in ALL_SENSOR_DESCRIPTIONS:
        _LOGGER.debug(
            "Registering entity: %s (%s)",
            description.key,
            description.translation_key,
        )
        entities.append(
            GarminConnectSensor(
                coordinator,
                unique_id,
                description,
            )
        )

    # Add gear sensors
    if "gear" in coordinator.data:
        for gear_item in coordinator.data["gear"]:
            name = gear_item["displayName"]
            sensor_type = gear_item["gearTypeName"]
            uuid = gear_item[Gear.UUID]
            unit = UnitOfLength.KILOMETERS
            icon = GEAR_ICONS.get(sensor_type, "mdi:shoe-print")
            device_class = SensorDeviceClass.DISTANCE
            state_class = SensorStateClass.TOTAL
            enabled_by_default = True

            _LOGGER.debug(
                "Registering gear entity: %s, %s, %s",
                sensor_type,
                name,
                uuid,
            )
            entities.append(
                GarminConnectGearSensor(
                    coordinator,
                    unique_id,
                    sensor_type,
                    name,
                    unit,
                    icon,
                    uuid,
                    device_class,
                    state_class,
                    enabled_by_default,
                )
            )

    async_add_entities(entities)
    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        "set_active_gear",
        {
            vol.Required("activity_type"): str,
            vol.Required("setting"): str,
        },
        "set_active_gear",
    )


class GarminConnectSensor(GarminConnectEntity, SensorEntity, RestoreEntity):
    """Representation of a Garmin Connect Sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        unique_id: str,
        description,
    ):
        """Initialize a Garmin Connect sensor."""
        super().__init__(coordinator, unique_id)
        self.entity_description = description
        self._attr_unique_id = f"{unique_id}_{description.key}"
        self._last_known_value: str | int | float | None = None

    async def async_added_to_hass(self) -> None:
        """Restore last known value when added to hass."""
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            if last_state.state not in ("unknown", "unavailable"):
                self._last_known_value = last_state.state

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if not self.coordinator.data:
            # Only return last known value if preserve_value is enabled
            if self.entity_description.preserve_value:
                return self._last_known_value
            return None

        # Use custom value function if provided in description
        if self.entity_description.value_fn:
            value = self.entity_description.value_fn(self.coordinator.data)
        else:
            value = self.coordinator.data.get(self.entity_description.key)

        if value is None:
            # Return last known value if preserve_value enabled (e.g., weight at midnight)
            if self.entity_description.preserve_value:
                return self._last_known_value
            return None

        # Handle timestamp device class
        if self.entity_description.device_class == SensorDeviceClass.TIMESTAMP:
            if value:
                try:
                    # Parse ISO format timestamp and set to UTC (GMT)
                    parsed = datetime.datetime.fromisoformat(value)
                    # If naive, assume UTC since Garmin returns GMT timestamps
                    if parsed.tzinfo is None:
                        value = parsed.replace(tzinfo=datetime.UTC)
                    else:
                        value = parsed
                except (ValueError, TypeError):
                    _LOGGER.debug("Could not parse timestamp: %s", value)
                    value = None

        # Preserve int types, only round floats
        if isinstance(value, int):
            self._last_known_value = value
            return value
        if isinstance(value, float):
            # Round floats to 1 decimal place, but return int if it's a whole number
            rounded = round(value, 1)
            if rounded == int(rounded):
                self._last_known_value = int(rounded)
                return int(rounded)
            self._last_known_value = rounded
            return rounded
        self._last_known_value = value
        return value

    @property
    def extra_state_attributes(self):
        """Return additional state attributes."""
        if not self.coordinator.data:
            return {}

        # Use custom attributes function if provided in description
        if self.entity_description.attributes_fn:
            return self.entity_description.attributes_fn(self.coordinator.data)

        # Default: just return last_synced
        return {
            "last_synced": self.coordinator.data.get("lastSyncTimestampGMT"),
        }

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        # Entity is available if coordinator has data
        # Individual sensors will show "Unknown" if their value is None
        return bool(super().available and self.coordinator.data)


class GarminConnectGearSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Garmin Connect Gear Sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        unique_id,
        sensor_type,
        name,
        unit,
        icon,
        uuid,
        device_class: None,
        state_class: None,
        enabled_default: bool = True,
    ):
        """Initialize a Garmin Connect Gear sensor."""
        super().__init__(coordinator)

        self._unique_id = unique_id
        self._type = sensor_type
        self._device_class = device_class
        self._state_class = state_class
        self._enabled_default = enabled_default
        self._uuid = uuid

        self._attr_name = name
        self._attr_device_class = self._device_class
        self._attr_icon = icon
        self._attr_native_unit_of_measurement = unit
        self._attr_unique_id = f"{self._unique_id}_{self._uuid}"
        self._attr_state_class = self._state_class

    @property
    def uuid(self):
        """Return the entity uuid"""
        return self._uuid

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if not self.coordinator.data or not self._stats():
            return None

        value = self._stats()["totalDistance"]
        return round(value / 1000, 2)

    @property
    def extra_state_attributes(self):
        """Return additional state attributes."""
        gear = self._gear()
        stats = self._stats()
        gear_defaults = self._gear_defaults()
        activity_types = self.coordinator.data["activityTypes"]
        default_for_activity = self._activity_names_for_gear_defaults(
            gear_defaults, activity_types)

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

        attributes["default_for_activity"] = (
            ", ".join(default_for_activity) if default_for_activity else "None"
        )

        return attributes

    def _activity_names_for_gear_defaults(self, gear_defaults, activity_types):
        """Get activity names for gear defaults."""
        activity_type_ids = [d["activityTypePk"] for d in gear_defaults]
        return [a["typeKey"] for a in activity_types if a["typeId"] in activity_type_ids]

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._unique_id)},
            name="Garmin Connect",
            manufacturer="Garmin",
            model="Garmin Connect",
            entry_type=None,
        )

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return self._enabled_default

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return bool(super().available and self.coordinator.data and self._gear())

    def _stats(self):
        """Get gear statistics from garmin"""
        for gear_stats_item in self.coordinator.data["gearStats"]:
            if gear_stats_item[Gear.UUID] == self._uuid:
                return gear_stats_item

    def _gear(self):
        """Get gear from garmin"""
        for gear_item in self.coordinator.data["gear"]:
            if gear_item[Gear.UUID] == self._uuid:
                return gear_item

    def _gear_defaults(self):
        """Return gear defaults for this UUID."""
        return list(
            filter(
                lambda d: d[Gear.UUID] == self.uuid and d["defaultGear"] is True,
                self.coordinator.data["gearDefaults"],
            )
        )

    async def set_active_gear(self, **kwargs):
        """Set this gear as active for an activity type."""
        activity_type = kwargs.get("activity_type")
        setting = kwargs.get("setting")

        if not await self.coordinator.async_login():
            raise IntegrationError(
                "Failed to login to Garmin Connect, unable to update")

        try:
            activity_type_id = next(
                filter(
                    lambda a: a[Gear.TYPE_KEY] == activity_type,
                    self.coordinator.data["activityTypes"],
                )
            )[Gear.TYPE_ID]
            if setting != ServiceSetting.ONLY_THIS_AS_DEFAULT:
                await self.hass.async_add_executor_job(
                    self.coordinator.api.set_gear_default,
                    activity_type_id,
                    self._uuid,
                    setting == ServiceSetting.DEFAULT,
                )
            else:
                old_default_state = await self.hass.async_add_executor_job(
                    self.coordinator.api.get_gear_defaults,
                    self.coordinator.data[Gear.USERPROFILE_ID],
                )
                to_deactivate = list(
                    filter(
                        lambda o: o[Gear.ACTIVITY_TYPE_PK] == activity_type_id
                        and o[Gear.UUID] != self._uuid,
                        old_default_state,
                    )
                )

                for active_gear in to_deactivate:
                    await self.hass.async_add_executor_job(
                        self.coordinator.api.set_gear_default,
                        activity_type_id,
                        active_gear[Gear.UUID],
                        False,
                    )
                await self.hass.async_add_executor_job(
                    self.coordinator.api.set_gear_default,
                    activity_type_id,
                    self._uuid,
                    True,
                )
        except Exception as err:
            raise IntegrationError(
                f"Failed to set active gear: {err}"
            ) from err

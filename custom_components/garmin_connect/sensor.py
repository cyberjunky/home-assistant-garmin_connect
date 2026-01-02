"""Platform for Garmin Connect integration."""

from __future__ import annotations

import datetime
import logging
from numbers import Number
from zoneinfo import ZoneInfo

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
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
import voluptuous as vol

from .const import (
    DATA_COORDINATOR,
    DOMAIN as GARMIN_DOMAIN,
    GEAR_ICONS,
    Gear,
    ServiceSetting,
)
from .entity import GarminConnectEntity
from .sensor_descriptions import (
    ALL_SENSOR_DESCRIPTIONS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    """Set up Garmin Connect sensor based on a config entry."""
    coordinator: DataUpdateCoordinator = hass.data[GARMIN_DOMAIN][entry.entry_id][DATA_COORDINATOR]
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

    platform.async_register_entity_service(
        "add_body_composition",
        {
            vol.Required("weight"): vol.Coerce(float),
            vol.Optional("timestamp"): str,
            vol.Optional("percent_fat"): vol.Coerce(float),
            vol.Optional("percent_hydration"): vol.Coerce(float),
            vol.Optional("visceral_fat_mass"): vol.Coerce(float),
            vol.Optional("bone_mass"): vol.Coerce(float),
            vol.Optional("muscle_mass"): vol.Coerce(float),
            vol.Optional("basal_met"): vol.Coerce(float),
            vol.Optional("active_met"): vol.Coerce(float),
            vol.Optional("physique_rating"): vol.Coerce(float),
            vol.Optional("metabolic_age"): vol.Coerce(float),
            vol.Optional("visceral_fat_rating"): vol.Coerce(float),
            vol.Optional("bmi"): vol.Coerce(float),
        },
        "add_body_composition",
    )

    platform.async_register_entity_service(
        "add_blood_pressure",
        {
            vol.Required("systolic"): int,
            vol.Required("diastolic"): int,
            vol.Required("pulse"): int,
            vol.Optional("timestamp"): str,
            vol.Optional("notes"): str,
        },
        "add_blood_pressure",
    )


class GarminConnectSensor(GarminConnectEntity, SensorEntity):
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

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None

        # Use custom value function if provided in description
        if self.entity_description.value_fn:
            value = self.entity_description.value_fn(self.coordinator.data)
        else:
            value = self.coordinator.data.get(self.entity_description.key)

        if value is None:
            return None

        # Handle timestamp device class
        if self.entity_description.device_class == SensorDeviceClass.TIMESTAMP:
            if value:
                value = datetime.datetime.fromisoformat(value).replace(
                    tzinfo=ZoneInfo(self.coordinator.time_zone)
                )

        return round(value, 2) if isinstance(value, Number) else value

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
        return (
            super().available
            and self.coordinator.data
            and self.entity_description.key in self.coordinator.data
        )

    async def add_body_composition(self, **kwargs):
        """Add a body composition measurement to Garmin Connect."""
        weight = kwargs.get("weight")
        timestamp = kwargs.get("timestamp")
        percent_fat = kwargs.get("percent_fat")
        percent_hydration = kwargs.get("percent_hydration")
        visceral_fat_mass = kwargs.get("visceral_fat_mass")
        bone_mass = kwargs.get("bone_mass")
        muscle_mass = kwargs.get("muscle_mass")
        basal_met = kwargs.get("basal_met")
        active_met = kwargs.get("active_met")
        physique_rating = kwargs.get("physique_rating")
        metabolic_age = kwargs.get("metabolic_age")
        visceral_fat_rating = kwargs.get("visceral_fat_rating")
        bmi = kwargs.get("bmi")

        """Check for login."""
        if not await self.coordinator.async_login():
            raise IntegrationError(
                "Failed to login to Garmin Connect, unable to update")

        """Record a weigh in/body composition."""
        await self.hass.async_add_executor_job(
            self.coordinator.api.add_body_composition,
            timestamp,
            weight,
            percent_fat,
            percent_hydration,
            visceral_fat_mass,
            bone_mass,
            muscle_mass,
            basal_met,
            active_met,
            physique_rating,
            metabolic_age,
            visceral_fat_rating,
            bmi,
        )

    async def add_blood_pressure(self, **kwargs):
        """Add a blood pressure measurement to Garmin Connect."""
        timestamp = kwargs.get("timestamp")
        systolic = kwargs.get("systolic")
        diastolic = kwargs.get("diastolic")
        pulse = kwargs.get("pulse")
        notes = kwargs.get("notes")

        """Check for login."""
        if not await self.coordinator.async_login():
            raise IntegrationError(
                "Failed to login to Garmin Connect, unable to update")

        """Record a blood pressure measurement."""
        await self.hass.async_add_executor_job(
            self.coordinator.api.set_blood_pressure,
            systolic,
            diastolic,
            pulse,
            timestamp,
            notes,
        )


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
            identifiers={(GARMIN_DOMAIN, self._unique_id)},
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
        return super().available and self.coordinator.data and self._gear()

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

        """Check for login."""
        if not await self.coordinator.async_login():
            raise IntegrationError(
                "Failed to login to Garmin Connect, unable to update")

        """Update Garmin Gear settings."""
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

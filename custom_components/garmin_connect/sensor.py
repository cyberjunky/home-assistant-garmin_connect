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
from homeassistant.const import ATTR_ENTITY_ID, CONF_ID, UnitOfLength
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
    CONF_SENSOR_GROUPS,
    DATA_COORDINATOR,
    DOMAIN as GARMIN_DOMAIN,
    GEAR_ICONS,
    Gear,
    ServiceSetting,
)
from .entity import GarminConnectEntity
from .sensor_descriptions import (
    ALL_SENSOR_DESCRIPTIONS,
    get_default_enabled_groups,
    get_sensors_for_groups,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    """Set up Garmin Connect sensor based on a config entry."""
    coordinator: DataUpdateCoordinator = hass.data[GARMIN_DOMAIN][entry.entry_id][DATA_COORDINATOR]
    unique_id = entry.data[CONF_ID]

    entities = []

    # Get enabled sensor groups from options, or use defaults for backward compatibility
    enabled_groups_list = entry.options.get(CONF_SENSOR_GROUPS)
    if enabled_groups_list is None:
        # Backward compatibility: if no options set, enable all default groups
        enabled_groups = get_default_enabled_groups()
    else:
        # Convert list back to set
        enabled_groups = set(enabled_groups_list)
    
    # Get sensor descriptions based on enabled groups
    sensor_descriptions = get_sensors_for_groups(enabled_groups)
    
    _LOGGER.debug(
        "Setting up sensors with enabled groups: %s (%d sensors)",
        enabled_groups,
        len(sensor_descriptions),
    )

    # Add main sensors using entity descriptions
    for description in sensor_descriptions:
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
            vol.Required(ATTR_ENTITY_ID): str,
            vol.Required("activity_type"): str,
            vol.Required("setting"): str,
        },
        "set_active_gear",
    )

    platform.async_register_entity_service(
        "add_body_composition",
        {
            vol.Required(ATTR_ENTITY_ID): str,
            vol.Optional("timestamp"): str,
            vol.Required("weight"): vol.Coerce(float),
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
            vol.Required(ATTR_ENTITY_ID): str,
            vol.Optional("timestamp"): str,
            vol.Required("systolic"): int,
            vol.Required("diastolic"): int,
            vol.Required("pulse"): int,
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
        """
        Return the current value of the sensor.

        Uses the entity description's value_fn if provided, otherwise applies
        type-specific formatting and conversions for backward compatibility.
        """
        if not self.coordinator.data:
            return None

        # Use custom value function if provided in description
        if self.entity_description.value_fn:
            return self.entity_description.value_fn(self.coordinator.data)

        # Fallback to legacy value extraction
        value = self.coordinator.data.get(self.entity_description.key)
        if value is None:
            return None

        # Legacy type-specific handling
        sensor_type = self.entity_description.key

        if sensor_type == "lastActivities" or sensor_type == "badges":
            value = len(self.coordinator.data[sensor_type])

        elif sensor_type == "lastActivity":
            value = self.coordinator.data[sensor_type]["activityName"]

        elif sensor_type == "enduranceScore":
            value = self.coordinator.data[sensor_type]["overallScore"]

        elif sensor_type == "nextAlarm":
            active_alarms = self.coordinator.data[sensor_type]
            if active_alarms:
                _LOGGER.debug("Active alarms: %s", active_alarms)
                _LOGGER.debug("Next alarm: %s", active_alarms[0])
                value = active_alarms[0]
            else:
                value = None

        # Handle timestamp device class
        if self.entity_description.device_class == SensorDeviceClass.TIMESTAMP:
            if value:
                value = datetime.datetime.fromisoformat(value).replace(
                    tzinfo=ZoneInfo(self.coordinator.time_zone)
                )

        return round(value, 2) if isinstance(value, Number) else value

    @property
    def extra_state_attributes(self):
        """
        Return additional state attributes for the sensor entity.

        Uses the entity description's attributes_fn if provided, otherwise
        returns sensor-specific attributes for backward compatibility.
        """
        if not self.coordinator.data:
            return {}

        # Use custom attributes function if provided in description
        if self.entity_description.attributes_fn:
            return self.entity_description.attributes_fn(self.coordinator.data)

        # Base attributes
        attributes = {
            "last_synced": self.coordinator.data["lastSyncTimestampGMT"],
        }

        sensor_type = self.entity_description.key

        # Only keep the last 5 activities for performance reasons
        if sensor_type == "lastActivities":
            activities = self.coordinator.data.get(sensor_type, [])
            sorted_activities = sorted(activities, key=lambda x: x["activityId"])
            attributes["last_activities"] = sorted_activities[-5:]

        elif sensor_type == "lastActivity":
            attributes = {**attributes, **self.coordinator.data[sensor_type]}

        # Only keep the last 10 badges for performance reasons
        elif sensor_type == "badges":
            badges = self.coordinator.data.get(sensor_type, [])
            sorted_badges = sorted(badges, key=lambda x: x["badgeEarnedDate"])
            attributes["badges"] = sorted_badges[-10:]

        elif sensor_type == "nextAlarm":
            attributes["next_alarms"] = self.coordinator.data[sensor_type]

        elif sensor_type == "enduranceScore":
            attributes = {**attributes, **self.coordinator.data[sensor_type]}
            del attributes["overallScore"]

        return attributes

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            super().available
            and self.coordinator.data
            and self.entity_description.key in self.coordinator.data
        )

    async def add_body_composition(self, **kwargs):
        """
        Add a new body composition measurement to Garmin Connect.

        Extracts body composition metrics from keyword arguments and submits them to the Garmin Connect API. Ensures the user is logged in before attempting to add the record.

        Raises:
            IntegrationError: If login to Garmin Connect fails.
        """
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
            raise IntegrationError("Failed to login to Garmin Connect, unable to update")

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
        """
        Add a blood pressure measurement to Garmin Connect using the provided values.

        Parameters:
            systolic: Systolic blood pressure value.
            diastolic: Diastolic blood pressure value.
            pulse: Pulse rate.
            timestamp: Optional timestamp for the measurement.
            notes: Optional notes for the measurement.

        Raises:
            IntegrationError: If unable to log in to Garmin Connect.
        """
        timestamp = kwargs.get("timestamp")
        systolic = kwargs.get("systolic")
        diastolic = kwargs.get("diastolic")
        pulse = kwargs.get("pulse")
        notes = kwargs.get("notes")

        """Check for login."""
        if not await self.coordinator.async_login():
            raise IntegrationError("Failed to login to Garmin Connect, unable to update")

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
        """
        Return additional state attributes for the gear sensor entity.

        Includes metadata such as last sync time, total activities, creation and update dates, gear make/model/status, custom model, maximum distance, and a comma-separated list of activity types for which this gear is set as default. Returns an empty dictionary if required data is missing.
        """
        gear = self._gear()
        stats = self._stats()
        gear_defaults = self._gear_defaults()
        activity_types = self.coordinator.data["activityTypes"]
        default_for_activity = self._activity_names_for_gear_defaults(gear_defaults, activity_types)

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
        """
        Return a list of default gear settings for this gear UUID.

        Returns:
            List of gear default dictionaries where this gear is set as the default.
        """
        return list(
            filter(
                lambda d: d[Gear.UUID] == self.uuid and d["defaultGear"] is True,
                self.coordinator.data["gearDefaults"],
            )
        )

    async def set_active_gear(self, **kwargs):
        """
        Set this gear as active or default for a specified activity type in Garmin Connect.

        Parameters:
            activity_type (str): The activity type key for which to update the gear setting.
            setting (str): The desired gear setting, indicating whether to set as default or as the only default.

        Raises:
            IntegrationError: If unable to log in to Garmin Connect.
        """
        activity_type = kwargs.get("activity_type")
        setting = kwargs.get("setting")

        """Check for login."""
        if not await self.coordinator.async_login():
            raise IntegrationError("Failed to login to Garmin Connect, unable to update")

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

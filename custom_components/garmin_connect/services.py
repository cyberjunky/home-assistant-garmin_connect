"""Services for Garmin Connect integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

if TYPE_CHECKING:
    from .coordinator import GarminConnectDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# Service schemas
SERVICE_ADD_BODY_COMPOSITION = "add_body_composition"
SERVICE_ADD_BLOOD_PRESSURE = "add_blood_pressure"
SERVICE_CREATE_ACTIVITY = "create_activity"

ADD_BODY_COMPOSITION_SCHEMA = vol.Schema(
    {
        vol.Required("weight"): vol.Coerce(float),
        vol.Optional("timestamp"): cv.string,
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
    }
)

ADD_BLOOD_PRESSURE_SCHEMA = vol.Schema(
    {
        vol.Required("systolic"): int,
        vol.Required("diastolic"): int,
        vol.Required("pulse"): int,
        vol.Optional("timestamp"): cv.string,
        vol.Optional("notes"): cv.string,
    }
)

CREATE_ACTIVITY_SCHEMA = vol.Schema(
    {
        vol.Required("activity_name"): cv.string,
        vol.Required("activity_type"): cv.string,
        vol.Required("start_datetime"): cv.string,
        vol.Required("duration_min"): int,
        vol.Optional("distance_km", default=0.0): vol.Coerce(float),
        vol.Optional("time_zone"): cv.string,
    }
)

SERVICE_UPLOAD_ACTIVITY = "upload_activity"
UPLOAD_ACTIVITY_SCHEMA = vol.Schema(
    {
        vol.Required("file_path"): cv.string,
    }
)


def _get_coordinator(hass: HomeAssistant) -> GarminConnectDataUpdateCoordinator:
    """Get the first available coordinator from config entries."""
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="no_integration_configured",
        )

    # Use the first config entry's coordinator
    entry = entries[0]
    if not hasattr(entry, "runtime_data") or entry.runtime_data is None:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="integration_not_loaded",
        )

    return entry.runtime_data  # type: ignore[no-any-return]


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up Garmin Connect services."""

    async def handle_add_body_composition(call: ServiceCall) -> None:
        """Handle add_body_composition service call."""
        coordinator = _get_coordinator(hass)

        weight = call.data.get("weight")
        timestamp = call.data.get("timestamp")
        percent_fat = call.data.get("percent_fat")
        percent_hydration = call.data.get("percent_hydration")
        visceral_fat_mass = call.data.get("visceral_fat_mass")
        bone_mass = call.data.get("bone_mass")
        muscle_mass = call.data.get("muscle_mass")
        basal_met = call.data.get("basal_met")
        active_met = call.data.get("active_met")
        physique_rating = call.data.get("physique_rating")
        metabolic_age = call.data.get("metabolic_age")
        visceral_fat_rating = call.data.get("visceral_fat_rating")
        bmi = call.data.get("bmi")

        if not await coordinator.async_login():
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="login_failed",
            )

        try:
            await hass.async_add_executor_job(
                coordinator.api.add_body_composition,
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
        except Exception as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="add_body_composition_failed",
                translation_placeholders={"error": str(err)},
            ) from err

    async def handle_add_blood_pressure(call: ServiceCall) -> None:
        """Handle add_blood_pressure service call."""
        coordinator = _get_coordinator(hass)

        systolic = call.data.get("systolic")
        diastolic = call.data.get("diastolic")
        pulse = call.data.get("pulse")
        timestamp = call.data.get("timestamp")
        notes = call.data.get("notes")

        if not await coordinator.async_login():
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="login_failed",
            )

        try:
            await hass.async_add_executor_job(
                coordinator.api.set_blood_pressure,
                systolic,
                diastolic,
                pulse,
                timestamp,
                notes,
            )
        except Exception as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="add_blood_pressure_failed",
                translation_placeholders={"error": str(err)},
            ) from err

    async def handle_create_activity(call: ServiceCall) -> None:
        """Handle create_activity service call."""
        coordinator = _get_coordinator(hass)

        activity_name = call.data.get("activity_name")
        activity_type = call.data.get("activity_type")
        start_datetime = call.data.get("start_datetime")
        # API requires milliseconds format: "2023-12-02T10:00:00.000"
        if start_datetime and "." not in start_datetime:
            start_datetime = f"{start_datetime}.000"
        duration_min = call.data.get("duration_min")
        distance_km = call.data.get("distance_km", 0.0)
        # Default to HA's configured timezone
        time_zone = call.data.get("time_zone") or str(hass.config.time_zone)

        if not await coordinator.async_login():
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="login_failed",
            )

        try:
            await hass.async_add_executor_job(
                coordinator.api.create_manual_activity,
                start_datetime,
                time_zone,
                activity_type,
                distance_km,
                duration_min,
                activity_name,
            )
        except Exception as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="create_activity_failed",
                translation_placeholders={"error": str(err)},
            ) from err

    async def handle_upload_activity(call: ServiceCall) -> None:
        """Handle upload_activity service call."""
        coordinator = _get_coordinator(hass)

        file_path = call.data.get("file_path")

        if not await coordinator.async_login():
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="login_failed",
            )

        # Check if file exists
        import os
        if not os.path.isfile(file_path):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="file_not_found",
                translation_placeholders={"file_path": file_path},
            )

        try:
            await hass.async_add_executor_job(
                coordinator.api.upload_activity,
                file_path,
            )
        except Exception as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="upload_activity_failed",
                translation_placeholders={"error": str(err)},
            ) from err

    # Register services
    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_BODY_COMPOSITION,
        handle_add_body_composition,
        schema=ADD_BODY_COMPOSITION_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_BLOOD_PRESSURE,
        handle_add_blood_pressure,
        schema=ADD_BLOOD_PRESSURE_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_CREATE_ACTIVITY,
        handle_create_activity,
        schema=CREATE_ACTIVITY_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_UPLOAD_ACTIVITY,
        handle_upload_activity,
        schema=UPLOAD_ACTIVITY_SCHEMA,
    )


async def async_unload_services(hass: HomeAssistant) -> None:
    """Unload Garmin Connect services."""
    hass.services.async_remove(DOMAIN, SERVICE_ADD_BODY_COMPOSITION)
    hass.services.async_remove(DOMAIN, SERVICE_ADD_BLOOD_PRESSURE)
    hass.services.async_remove(DOMAIN, SERVICE_CREATE_ACTIVITY)
    hass.services.async_remove(DOMAIN, SERVICE_UPLOAD_ACTIVITY)

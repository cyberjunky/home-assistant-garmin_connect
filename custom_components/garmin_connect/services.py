"""Services for Garmin Connect integration."""

import logging

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Service schemas
SERVICE_ADD_BODY_COMPOSITION = "add_body_composition"
SERVICE_ADD_BLOOD_PRESSURE = "add_blood_pressure"

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


def _get_coordinator(hass: HomeAssistant):
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

    return entry.runtime_data


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


async def async_unload_services(hass: HomeAssistant) -> None:
    """Unload Garmin Connect services."""
    hass.services.async_remove(DOMAIN, SERVICE_ADD_BODY_COMPOSITION)
    hass.services.async_remove(DOMAIN, SERVICE_ADD_BLOOD_PRESSURE)

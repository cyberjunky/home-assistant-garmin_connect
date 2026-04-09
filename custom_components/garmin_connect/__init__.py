"""The Garmin Connect integration."""

from __future__ import annotations

import asyncio
import logging

from ha_garmin import GarminAuth, GarminClient
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import CONF_CLIENT_ID, CONF_REFRESH_TOKEN, CONF_TOKEN, DOMAIN
from .coordinator import (
    ActivityCoordinator,
    BloodPressureCoordinator,
    BodyCoordinator,
    CoreCoordinator,
    GarminConnectConfigEntry,
    GarminConnectCoordinators,
    GearCoordinator,
    GoalsCoordinator,
    MenstrualCoordinator,
    TrainingCoordinator,
)
from .services import async_setup_services, async_unload_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

# Mapping of old sensor keys (v1) to new sensor keys (v2).
# Keys present in both versions are migrated by unique_id prefix only.
# Keys listed here were renamed between versions.
_V1_KEY_RENAMES: dict[str, str | None] = {
    "activeSeconds": "activeMinutes",
    "activityStressDuration": "activityStressMinutes",
    "boneMass": "boneMassKg",
    "highStressDuration": "highStressMinutes",
    "highlyActiveSeconds": "highlyActiveMinutes",
    "hrvStatus": "hrvStatusText",
    "latestRespirationTimeGMT": "latestRespirationTime",
    "latestSpo2ReadingTimeLocal": "latestSpo2ReadingTime",
    "lowStressDuration": "lowStressMinutes",
    "measurableAsleepDuration": "measurableAsleepDurationMinutes",
    "measurableAwakeDuration": "measurableAwakeDurationMinutes",
    "mediumStressDuration": "mediumStressMinutes",
    "muscleMass": "muscleMassKg",
    "restStressDuration": "restStressMinutes",
    "sedentarySeconds": "sedentaryMinutes",
    "sleepTimeSeconds": "sleepTimeMinutes",
    "sleepingSeconds": "sleepingMinutes",
    "stressDuration": "stressMinutes",
    "stressQualifier": "stressQualifierText",
    "totalStressDuration": "stressMinutes",
    "uncategorizedStressDuration": "uncategorizedStressMinutes",
    "wellnessEndTimeLocal": "wellnessEndTime",
    "wellnessStartTimeLocal": "wellnessStartTime",
    # Dropped sensors (no equivalent in v2)
    "netCalorieGoal": None,
    "netRemainingKilocalories": None,
    "wellnessDescription": None,
}


async def async_migrate_entry(hass: HomeAssistant, entry: GarminConnectConfigEntry) -> bool:
    """Migrate a config entry from v1 to v2.

    V1 used garminconnect/garth (OAuth1 tokens, email as unique_id prefix).
    V2 uses ha-garmin (DI tokens, entry_id as unique_id prefix).

    Tokens are incompatible so reauth is required. Entity unique_ids are
    migrated in the entity registry so existing entity_ids are preserved.
    """
    if entry.version == 1:
        _LOGGER.info("Migrating Garmin Connect entry %s from v1 to v2", entry.title)

        # The old unique_id was the email address; it's also used as the
        # prefix for all entity unique_ids (e.g. "user@example.com_totalSteps").
        old_prefix = entry.unique_id or ""

        if old_prefix:
            _migrate_entity_unique_ids(hass, entry, old_prefix)

        # Bump version and trigger reauth (tokens are incompatible).
        hass.config_entries.async_update_entry(entry, version=2)
        entry.async_start_reauth(hass)
        _LOGGER.info("Migration to v2 complete for %s — reauth required", entry.title)

    return True


def _migrate_entity_unique_ids(
    hass: HomeAssistant,
    entry: GarminConnectConfigEntry,
    old_prefix: str,
) -> None:
    """Rewrite entity unique_ids from v1 (email_key) to v2 (entry_id_key).

    Also applies key renames so the entity registry keeps existing entity_ids
    intact (e.g. sensor.total_steps stays sensor.total_steps).
    """
    registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(registry, entry.entry_id)
    new_prefix = entry.entry_id

    for entity in entities:
        old_uid = entity.unique_id
        if not old_uid.startswith(old_prefix + "_"):
            continue

        old_key = old_uid[len(old_prefix) + 1 :]

        # Determine the new key: renamed, dropped, or unchanged.
        if old_key in _V1_KEY_RENAMES:
            new_key = _V1_KEY_RENAMES[old_key]
            if new_key is None:
                _LOGGER.debug(
                    "Sensor %s (%s) has been removed in v2, skipping",
                    entity.entity_id,
                    old_key,
                )
                continue
        else:
            new_key = old_key

        new_uid = f"{new_prefix}_{new_key}"

        if new_uid == old_uid:
            continue

        try:
            registry.async_update_entity(entity.entity_id, new_unique_id=new_uid)
            _LOGGER.debug(
                "Migrated %s unique_id: %s -> %s",
                entity.entity_id,
                old_uid,
                new_uid,
            )
        except ValueError:
            _LOGGER.warning(
                "Could not migrate %s (%s -> %s): unique_id conflict",
                entity.entity_id,
                old_uid,
                new_uid,
            )


async def async_setup_entry(hass: HomeAssistant, entry: GarminConnectConfigEntry) -> bool:
    """Set up Garmin Connect from a config entry."""
    if CONF_TOKEN not in entry.data:
        # Migration from v1 bumps version and starts reauth but setup still runs.
        # Without valid DI tokens there's nothing to set up — reauth will fix it.
        _LOGGER.debug("Skipping setup for %s — reauth pending", entry.title)
        return False

    is_cn = hass.config.country == "CN"
    auth = GarminAuth(is_cn=is_cn)
    auth.di_token = entry.data[CONF_TOKEN]
    auth.di_refresh_token = entry.data[CONF_REFRESH_TOKEN]
    auth.di_client_id = entry.data[CONF_CLIENT_ID]

    client = GarminClient(auth, is_cn=is_cn)

    coordinators = GarminConnectCoordinators(
        core=CoreCoordinator(hass, entry, client, auth),
        activity=ActivityCoordinator(hass, entry, client, auth),
        training=TrainingCoordinator(hass, entry, client, auth),
        body=BodyCoordinator(hass, entry, client, auth),
        goals=GoalsCoordinator(hass, entry, client, auth),
        gear=GearCoordinator(hass, entry, client, auth),
        blood_pressure=BloodPressureCoordinator(hass, entry, client, auth),
        menstrual=MenstrualCoordinator(hass, entry, client, auth),
    )

    await asyncio.gather(
        coordinators.core.async_config_entry_first_refresh(),
        coordinators.activity.async_config_entry_first_refresh(),
        coordinators.training.async_config_entry_first_refresh(),
        coordinators.body.async_config_entry_first_refresh(),
        coordinators.goals.async_config_entry_first_refresh(),
        coordinators.gear.async_config_entry_first_refresh(),
        coordinators.blood_pressure.async_config_entry_first_refresh(),
        coordinators.menstrual.async_config_entry_first_refresh(),
    )

    entry.runtime_data = coordinators

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if not hass.services.has_service(DOMAIN, "set_active_gear"):
        await async_setup_services(hass)

    entry.async_on_unload(entry.add_update_listener(async_options_update_listener))

    return True


async def async_options_update_listener(
    hass: HomeAssistant, entry: GarminConnectConfigEntry
) -> None:
    """Handle options update — reload to apply new scan_interval."""
    hass.async_create_task(hass.config_entries.async_reload(entry.entry_id))


async def async_unload_entry(hass: HomeAssistant, entry: GarminConnectConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok and len(hass.config_entries.async_entries(DOMAIN)) == 1:
        await async_unload_services(hass)

    return unload_ok

"""The Garmin Connect integration."""

from __future__ import annotations

import logging

from aiohttp import ClientError
from ha_garmin import GarminAuth, GarminClient
from ha_garmin.exceptions import GarminConnectError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_DI_CLIENT_ID, CONF_DI_REFRESH_TOKEN, CONF_DI_TOKEN
from .coordinator import CoreCoordinator, GarminConnectCoordinators

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

type GarminConnectConfigEntry = ConfigEntry[GarminConnectCoordinators]


async def async_migrate_entry(
    hass: HomeAssistant, entry: GarminConnectConfigEntry
) -> bool:
    """Migrate config entry to the current version."""
    if CONF_DI_TOKEN not in entry.data:
        _LOGGER.warning(
            "Garmin Connect config entry %s uses an old format "
            "and needs to be re-authenticated",
            entry.entry_id,
        )
        entry.async_start_reauth(hass)
        return False

    if entry.version < 2:
        # v1 used email as unique_id; v2 uses numeric profile_id.
        unique_id = entry.unique_id
        try:
            is_cn = hass.config.country == "CN"
            auth = GarminAuth(is_cn=is_cn)
            auth.di_token = entry.data[CONF_DI_TOKEN]
            auth.di_refresh_token = entry.data[CONF_DI_REFRESH_TOKEN]
            auth.di_client_id = entry.data[CONF_DI_CLIENT_ID]
            client = GarminClient(auth, is_cn=is_cn)
            profile = await client.get_user_profile()
            unique_id = str(profile.profile_id)
        except (GarminConnectError, ClientError):
            _LOGGER.warning(
                "Could not fetch Garmin profile during migration of entry %s; "
                "keeping existing unique_id",
                entry.entry_id,
            )
        hass.config_entries.async_update_entry(entry, unique_id=unique_id, version=2)

    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: GarminConnectConfigEntry
) -> bool:
    """Set up Garmin Connect from a config entry."""
    is_cn = hass.config.country == "CN"
    auth = GarminAuth(is_cn=is_cn)
    auth.di_token = entry.data[CONF_DI_TOKEN]
    auth.di_refresh_token = entry.data[CONF_DI_REFRESH_TOKEN]
    auth.di_client_id = entry.data[CONF_DI_CLIENT_ID]

    client = GarminClient(auth, is_cn=is_cn)

    coordinators = GarminConnectCoordinators(
        core=CoreCoordinator(hass, entry, client, auth),
    )

    await coordinators.core.async_config_entry_first_refresh()

    entry.runtime_data = coordinators

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: GarminConnectConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

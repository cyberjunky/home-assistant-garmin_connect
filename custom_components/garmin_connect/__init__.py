"""The Garmin Connect integration."""

import logging

from garminconnect import Garmin
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ID, CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import GarminConnectDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old config entry to new format."""
    _LOGGER.debug("Migrating config entry from version %s", entry.version)

    if entry.version == 1:
        # Has USERNAME + PASSWORD but no TOKEN (old auth method)
        if (
            CONF_TOKEN not in entry.data
            and CONF_USERNAME in entry.data
            and CONF_PASSWORD in entry.data
        ):
            _LOGGER.info("Migrating from username/password to token-based auth")

            username = entry.data[CONF_USERNAME]
            password = entry.data[CONF_PASSWORD]
            in_china = hass.config.country == "CN"

            api = Garmin(email=username, password=password, is_cn=in_china)

            try:
                await hass.async_add_executor_job(api.login)
                tokens = api.garth.dumps()

                new_data = {
                    CONF_ID: entry.data.get(CONF_ID, username),
                    CONF_TOKEN: tokens,
                }

                hass.config_entries.async_update_entry(entry, data=new_data)
                _LOGGER.info("Migration successful")
                return True

            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.error("Migration failed: %s", err)
                return False

        # Has USERNAME + TOKEN but no ID (partially migrated)
        elif (
            CONF_ID not in entry.data
            and CONF_USERNAME in entry.data
            and CONF_TOKEN in entry.data
        ):
            _LOGGER.info("Migrating: converting USERNAME to ID")

            new_data = {
                CONF_ID: entry.data[CONF_USERNAME],
                CONF_TOKEN: entry.data[CONF_TOKEN],
            }

            hass.config_entries.async_update_entry(entry, data=new_data)
            return True

        # Missing TOKEN (incomplete/corrupted)
        elif CONF_TOKEN not in entry.data:
            if CONF_ID not in entry.data:
                _LOGGER.info("Adding placeholder ID for reauth flow")
                new_data = {
                    **entry.data,
                    CONF_ID: entry.entry_id,
                }
                hass.config_entries.async_update_entry(entry, data=new_data)

            _LOGGER.info("Config entry incomplete, reauthentication required")
            return True

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Garmin Connect from a config entry."""
    coordinator = GarminConnectDataUpdateCoordinator(hass, entry=entry)

    if not await coordinator.async_login():
        return False

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {DATA_COORDINATOR: coordinator}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok

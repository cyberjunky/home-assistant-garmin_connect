"""The Garmin Connect integration."""
from datetime import date
import logging

from garminconnect_ha import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DATA_COORDINATOR, DEFAULT_UPDATE_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Garmin Connect from a config entry."""

    username: str = entry.data[CONF_USERNAME]
    password: str = entry.data[CONF_PASSWORD]

    api = Garmin(username, password)
    try:
        await hass.async_add_executor_job(api.login)
    except (
        GarminConnectAuthenticationError,
        GarminConnectTooManyRequestsError,
    ) as err:
        _LOGGER.error("Error occurred during Garmin Connect login request: %s", err)
        return False
    except (GarminConnectConnectionError) as err:
        _LOGGER.error(
            "Connection error occurred during Garmin Connect login request: %s", err
        )
        raise ConfigEntryNotReady from err
    except Exception:  # pylint: disable=broad-except
        _LOGGER.exception("Unknown error occurred during Garmin Connect login request")
        return False

    async def async_update_data():
        _LOGGER.debug("Updating data for %s", username)
        return await async_update_garmin_data(hass, api)

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=username,
        update_method=async_update_data,
        update_interval=DEFAULT_UPDATE_INTERVAL,
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        DATA_COORDINATOR: coordinator,
    }

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_update_garmin_data(hass, api):
    """Fetch data from API endpoint."""
    try:
        summary = await hass.async_add_executor_job(
            api.get_user_summary, date.today().isoformat()
        )
        body = await hass.async_add_executor_job(
            api.get_body_composition, date.today().isoformat()
        )
        alarms = await hass.async_add_executor_job(api.get_device_alarms)
    except (
        GarminConnectAuthenticationError,
        GarminConnectTooManyRequestsError,
        GarminConnectConnectionError,
    ) as error:
        raise UpdateFailed(error) from error

    return {
        **summary,
        **body["totalAverage"],
        "nextAlarm": alarms,
    }

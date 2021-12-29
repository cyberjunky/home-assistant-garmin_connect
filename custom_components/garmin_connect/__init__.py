"""The Garmin Connect integration."""
from datetime import date
import logging

from garminconnect import (
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

    coordinator = GarminConnectDataUpdateCoordinator(hass, entry=entry)

    if not await coordinator.async_login():
        return False

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


class GarminConnectDataUpdateCoordinator(DataUpdateCoordinator):
    """Garmin Connect Data Update Coordinator."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the Garmin Connect hub."""
        self.entry = entry
        self.hass = hass

        self._api = Garmin(entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])

        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=DEFAULT_UPDATE_INTERVAL
        )

    async def async_login(self) -> bool:
        """Login to Garmin Connect."""
        try:
            await self.hass.async_add_executor_job(self._api.login)
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
            _LOGGER.exception(
                "Unknown error occurred during Garmin Connect login request"
            )
            return False

        return True

    async def _async_update_data(self) -> dict:
        """Fetch data from Garmin Connect."""
        try:
            summary = await self.hass.async_add_executor_job(
                self._api.get_user_summary, date.today().isoformat()
            )
            body = await self.hass.async_add_executor_job(
                self._api.get_body_composition, date.today().isoformat()
            )
            alarms = await self.hass.async_add_executor_job(self._api.get_device_alarms)
        except (
            GarminConnectAuthenticationError,
            GarminConnectTooManyRequestsError,
            GarminConnectConnectionError,
        ) as error:
            _LOGGER.debug("Trying to relogin to Garmin Connect")
            if not await self.async_login():
                raise UpdateFailed(error) from error
            return {}

        return {
            **summary,
            **body["totalAverage"],
            "nextAlarm": alarms,
        }

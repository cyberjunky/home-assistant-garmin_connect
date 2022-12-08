"""The Garmin Connect integration."""
from datetime import date
import logging
import asyncio
from collections.abc import Awaitable

from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, IntegrationError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DATA_COORDINATOR,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    GEAR,
    SERVICE_SETTING,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Garmin Connect from a config entry."""

    coordinator = GarminConnectDataUpdateCoordinator(hass, entry=entry)

    if not await coordinator.async_login():
        return False

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {DATA_COORDINATOR: coordinator}

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
            gear = await self.hass.async_add_executor_job(
                self._api.get_gear, summary[GEAR.USERPROFILE_ID]
            )
            tasks: list[Awaitable] = [
                self.hass.async_add_executor_job(
                    self._api.get_gear_stats, gear_item[GEAR.UUID]
                )
                for gear_item in gear
            ]
            gear_stats = await asyncio.gather(*tasks)
            activity_types = await self.hass.async_add_executor_job(
                self._api.get_activity_types
            )
            gear_defaults = await self.hass.async_add_executor_job(
                self._api.get_gear_defaults, summary[GEAR.USERPROFILE_ID]
            )
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
            "gear": gear,
            "gear_stats": gear_stats,
            "activity_types": activity_types,
            "gear_defaults": gear_defaults,
        }

    async def set_active_gear(self, entity, service_data):
        """Update Garmin Gear settings"""
        if not await self.async_login():
            raise IntegrationError(
                "Failed to login to Garmin Connect, unable to update"
            )

        setting = service_data.data["setting"]
        activity_type_id = next(
            filter(
                lambda a: a[GEAR.TYPE_KEY] == service_data.data["activity_type"],
                self.data["activity_types"],
            )
        )[GEAR.TYPE_ID]
        if setting != SERVICE_SETTING.ONLY_THIS_AS_DEFAULT:
            await self.hass.async_add_executor_job(
                self._api.set_gear_default,
                activity_type_id,
                entity.uuid,
                setting == SERVICE_SETTING.DEFAULT,
            )
        else:
            old_default_state = await self.hass.async_add_executor_job(
                self._api.get_gear_defaults, self.data[GEAR.USERPROFILE_ID]
            )
            to_deactivate = list(
                filter(
                    lambda o: o[GEAR.ACTIVITY_TYPE_PK] == activity_type_id
                    and o[GEAR.UUID] != entity.uuid,
                    old_default_state,
                )
            )

            for active_gear in to_deactivate:
                await self.hass.async_add_executor_job(
                    self._api.set_gear_default,
                    activity_type_id,
                    active_gear[GEAR.UUID],
                    False,
                )
            await self.hass.async_add_executor_job(
                self._api.set_gear_default, activity_type_id, entity.uuid, True
            )

"""The Garmin Connect integration."""

import asyncio
from collections.abc import Awaitable
from datetime import datetime, timedelta
import logging
from zoneinfo import ZoneInfo

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

from .const import (
    DATA_COORDINATOR,
    DAY_TO_NUMBER,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    Gear,
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

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

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
        self.in_china = False

        self.country = self.hass.config.country
        if self.country == "CN":
            self.in_china = True
        _LOGGER.debug("Country: %s", self.country)

        self.time_zone = self.hass.config.time_zone
        _LOGGER.debug("Time zone: %s", self.time_zone)

        self.api = Garmin(entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD], self.in_china)

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=DEFAULT_UPDATE_INTERVAL)

    async def async_login(self) -> bool:
        """Login to Garmin Connect."""
        try:
            await self.hass.async_add_executor_job(self.api.login)
        except (
            GarminConnectAuthenticationError,
            GarminConnectTooManyRequestsError,
        ) as err:
            _LOGGER.error("Error occurred during Garmin Connect login request: %s", err)
            return False
        except GarminConnectConnectionError as err:
            _LOGGER.error("Connection error occurred during Garmin Connect login request: %s", err)
            raise ConfigEntryNotReady from err
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unknown error occurred during Garmin Connect login request")
            return False

        return True

    async def _async_update_data(self) -> dict:
        """Fetch data from Garmin Connect."""
        summary = {}
        body = {}
        alarms = {}
        gear = {}
        gear_stats = {}
        gear_defaults = {}
        activity_types = {}
        sleep_data = {}
        sleep_score = None
        sleep_time_seconds = None
        hrv_data = {}
        hrv_status = {"status": "unknown"}
        next_alarms = []

        today = datetime.now(ZoneInfo(self.time_zone)).date()

        try:
            summary = await self.hass.async_add_executor_job(
                self.api.get_user_summary, today.isoformat()
            )
            _LOGGER.debug("Summary data fetched: %s", summary)

            body = await self.hass.async_add_executor_job(
                self.api.get_body_composition, today.isoformat()
            )
            _LOGGER.debug("Body data fetched: %s", body)

            activities = await self.hass.async_add_executor_job(
                self.api.get_activities_by_date,
                (today - timedelta(days=7)).isoformat(),
                (today + timedelta(days=1)).isoformat(),
            )
            _LOGGER.debug("Activities data fetched: %s", activities)
            summary["lastActivities"] = activities

            badges = await self.hass.async_add_executor_job(self.api.get_earned_badges)
            _LOGGER.debug("Badges data fetched: %s", badges)
            summary["badges"] = badges

            alarms = await self.hass.async_add_executor_job(self.api.get_device_alarms)
            _LOGGER.debug("Alarms data fetched: %s", alarms)

            next_alarms = calculate_next_active_alarms(alarms, self.time_zone)

            activity_types = await self.hass.async_add_executor_job(self.api.get_activity_types)
            _LOGGER.debug("Activity types data fetched: %s", activity_types)

            sleep_data = await self.hass.async_add_executor_job(
                self.api.get_sleep_data, today.isoformat()
            )
            _LOGGER.debug("Sleep data fetched: %s", sleep_data)

            hrv_data = await self.hass.async_add_executor_job(
                self.api.get_hrv_data, today.isoformat()
            )
            _LOGGER.debug("HRV data fetched: %s", hrv_data)
        except (
            GarminConnectAuthenticationError,
            GarminConnectTooManyRequestsError,
            GarminConnectConnectionError,
        ) as error:
            _LOGGER.debug("Trying to relogin to Garmin Connect")
            if not await self.async_login():
                raise UpdateFailed(error) from error

        try:
            gear = await self.hass.async_add_executor_job(
                self.api.get_gear, summary[Gear.USERPROFILE_ID]
            )
            _LOGGER.debug("Gear data fetched: %s", gear)

            tasks: list[Awaitable] = [
                self.hass.async_add_executor_job(self.api.get_gear_stats, gear_item[Gear.UUID])
                for gear_item in gear
            ]
            gear_stats = await asyncio.gather(*tasks)
            _LOGGER.debug("Gear stats data fetched: %s", gear_stats)

            gear_defaults = await self.hass.async_add_executor_job(
                self.api.get_gear_defaults, summary[Gear.USERPROFILE_ID]
            )
            _LOGGER.debug("Gear defaults data fetched: %s", gear_defaults)
        except (KeyError, TypeError, ValueError, ConnectionError) as err:
            _LOGGER.debug("Gear data is not available: %s", err)

        try:
            sleep_score = sleep_data["dailySleepDTO"]["sleepScores"]["overall"]["value"]
            _LOGGER.debug("Sleep score data: %s", sleep_score)
        except KeyError:
            _LOGGER.debug("Sleep score data is not available")

        try:
            sleep_time_seconds = sleep_data["dailySleepDTO"]["sleepTimeSeconds"]
            _LOGGER.debug("Sleep time seconds data: %s", sleep_time_seconds)
        except KeyError:
            _LOGGER.debug("Sleep time seconds data is not available")

        try:
            if hrv_data and "hrvSummary" in hrv_data:
                hrv_status = hrv_data["hrvSummary"]
                _LOGGER.debug("HRV summary: %s", hrv_status)
        except KeyError:
            _LOGGER.debug("HRV data is not available")

        return {
            **summary,
            **body["totalAverage"],
            "nextAlarm": next_alarms,
            "gear": gear,
            "gear_stats": gear_stats,
            "activity_types": activity_types,
            "gear_defaults": gear_defaults,
            "sleepScore": sleep_score,
            "sleepTimeSeconds": sleep_time_seconds,
            "hrvStatus": hrv_status,
        }


def calculate_next_active_alarms(alarms, time_zone):
    """
    Calculate garmin next active alarms from settings.
    Alarms are sorted by time.

    Example of alarms data:
    Alarms data fetched: [{'alarmMode': 'OFF', 'alarmTime': 1233, 'alarmDays': ['ONCE'], 'alarmSound': 'TONE_AND_VIBRATION', 'alarmId': 1737308355, 'changeState': 'UNCHANGED', 'backlight': 'ON', 'enabled': None, 'alarmMessage': None, 'alarmImageId': None, 'alarmIcon': None, 'alarmType': None}]
    """
    active_alarms = []
    now = datetime.now(ZoneInfo(time_zone))
    _LOGGER.debug("Now: %s, Alarms: %s", now, alarms)

    for alarm_setting in alarms:
        if alarm_setting["alarmMode"] != "ON":
            continue

        for day in alarm_setting["alarmDays"]:
            alarm_time = alarm_setting["alarmTime"]
            _LOGGER.debug("Alarm time: %s, Alarm day: %s", alarm_time, day)
            if day == "ONCE":
                midnight = datetime.combine(
                    now.date(), datetime.min.time(), tzinfo=ZoneInfo(time_zone)
                )

                alarm = midnight + timedelta(minutes=alarm_time)
                _LOGGER.debug("Midnight: %s, Alarm: %s", midnight, alarm_time)

                # If the alarm time is in the past, move it to the next day
                if alarm < now:
                    alarm += timedelta(days=1)
            else:
                start_of_week = datetime.combine(
                    now.date() - timedelta(days=now.date().isoweekday() % 7),
                    datetime.min.time(),
                    tzinfo=ZoneInfo(time_zone),
                )

                days_to_add = DAY_TO_NUMBER[day] % 7
                alarm = start_of_week + timedelta(minutes=alarm_time, days=days_to_add)
                _LOGGER.debug("Start of week: %s, Alarm: %s", start_of_week, alarm)

                # If the alarm time is in the past, move it to the next week
                if alarm < now:
                    alarm += timedelta(days=7)

            active_alarms.append(alarm.isoformat())

    return sorted(active_alarms) if active_alarms else None

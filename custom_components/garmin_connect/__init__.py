"""The Garmin Connect integration."""

import asyncio
from collections.abc import Awaitable
from datetime import datetime, timedelta
import logging
from zoneinfo import ZoneInfo
import requests
from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from .const import (
    DATA_COORDINATOR,
    DAY_TO_NUMBER,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    LEVEL_POINTS,
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
        self._in_china = False

        # Check if the user resides in China
        country = self.hass.config.country
        if country == "CN":
            self._in_china = True
        _LOGGER.debug("Country: %s", country)

        self.time_zone = self.hass.config.time_zone
        _LOGGER.debug("Time zone: %s", self.time_zone)

        self.api = Garmin(is_cn=self._in_china)

        super().__init__(hass, _LOGGER, name=DOMAIN,
                         update_interval=DEFAULT_UPDATE_INTERVAL)

    async def async_login(self) -> bool:
        """Login to Garmin Connect."""
        try:
            # Check if the token exists in the entry data
            if CONF_TOKEN not in self.entry.data:
                raise KeyError("Token not found, migrating config entry")

            await self.hass.async_add_executor_job(self.api.login, self.entry.data[CONF_TOKEN])
        except GarminConnectAuthenticationError as err:
            _LOGGER.error(
                "Authentication error occurred during login: %s", err.response.text)
            raise ConfigEntryAuthFailed from err
        except GarminConnectTooManyRequestsError as err:
            _LOGGER.error(
                "Too many request error occurred during login: %s", err)
            return False
        except GarminConnectConnectionError as err:
            _LOGGER.error(
                "Connection error occurred during login: %s", err)
            raise ConfigEntryNotReady from err
        except requests.exceptions.HTTPError as err:
            if err.response.status_code == 401:
                _LOGGER.error(
                    "Authentication error occurred during login: %s", err.response.text)
                raise ConfigEntryAuthFailed from err
            if err.response.status_code == 429:
                _LOGGER.error(
                    "Too many requests error occurred during login: %s", err.response.text)
                return False
            _LOGGER.error(
                "Unknown HTTP error occurred during login: %s", err)
            return False
        except KeyError as err:
            _LOGGER.error(
                "Found old config during login: %s", err)
            raise ConfigEntryAuthFailed from err
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.exception(
                "Unknown error occurred during login: %s", err)
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
        last_activities = []
        sleep_data = {}
        sleep_score = None
        sleep_time_seconds = None
        hrv_data = {}
        hrv_status = {"status": "unknown"}
        next_alarms = []

        today = datetime.now(ZoneInfo(self.time_zone)).date()

        try:
            # User summary
            summary = await self.hass.async_add_executor_job(
                self.api.get_user_summary, today.isoformat()
            )
            if summary:
                _LOGGER.debug("User summary data fetched: %s", summary)
            else:
                _LOGGER.debug("No user summary data found")

            # Body composition
            body = await self.hass.async_add_executor_job(
                self.api.get_body_composition, today.isoformat()
            )
            if body:
                _LOGGER.debug("Body data fetched: %s", body)
            else:
                _LOGGER.debug("No body data found")

            # Last activities
            last_activities = await self.hass.async_add_executor_job(
                self.api.get_activities_by_date,
                (today - timedelta(days=7)).isoformat(),
                (today + timedelta(days=1)).isoformat(),
            )
            if last_activities:
                _LOGGER.debug("Last activities data fetched: %s",
                              last_activities)
            else:
                _LOGGER.debug("No last activities data found")

            # Add last activities to summary
            summary["lastActivities"] = last_activities
            summary["lastActivity"] = last_activities[0] if last_activities else {}

            # Badges
            badges = await self.hass.async_add_executor_job(self.api.get_earned_badges)
            if badges:
                _LOGGER.debug("Badges data fetched: %s", badges)
            else:
                _LOGGER.debug("No badges data found")

            # Add badges to summary
            summary["badges"] = badges

            # Calculate user points and user level
            user_points = 0
            for badge in badges:
                user_points += badge["badgePoints"] * \
                    badge["badgeEarnedNumber"]

            # Add user points to summary
            summary["userPoints"] = user_points

            user_level = 0
            for level, points in LEVEL_POINTS.items():
                if user_points >= points:
                    user_level = level

            # Add user level to summary
            summary["userLevel"] = user_level

            # Alarms
            alarms = await self.hass.async_add_executor_job(self.api.get_device_alarms)
            if alarms:
                _LOGGER.debug("Alarms data fetched: %s", alarms)
            else:
                _LOGGER.debug("No alarms data found")

            # Add alarms to summary
            next_alarms = calculate_next_active_alarms(alarms, self.time_zone)

            # Activity types
            activity_types = await self.hass.async_add_executor_job(self.api.get_activity_types)
            if activity_types:
                _LOGGER.debug("Activity types data fetched: %s",
                              activity_types)
            else:
                _LOGGER.debug("No activity types data found")

            # Sleep data
            sleep_data = await self.hass.async_add_executor_job(
                self.api.get_sleep_data, today.isoformat()
            )
            if sleep_data:
                _LOGGER.debug("Sleep data fetched: %s", sleep_data)
            else:
                _LOGGER.debug("No sleep data found")

            # HRV data
            hrv_data = await self.hass.async_add_executor_job(
                self.api.get_hrv_data, today.isoformat()
            )
            if hrv_data:
                _LOGGER.debug("HRV data fetched: %s", hrv_data)
            else:
                _LOGGER.debug("No HRV data found")

            # Fitness age data
            fitnessage_data = await self.hass.async_add_executor_job(
                self.api.get_fitnessage_data, today.isoformat()
            )
            if fitnessage_data:
                _LOGGER.debug("Fitness age data fetched: %s", fitnessage_data)
            else:
                _LOGGER.debug("No fitness age data found")

            # Hyrdation data
            hydration_data = await self.hass.async_add_executor_job(
                self.api.get_hydration_data, today.isoformat()
            )
            if hydration_data:
                _LOGGER.debug("Hydration data fetched: %s", hydration_data)
            else:
                _LOGGER.debug("No hydration data found")

        except GarminConnectAuthenticationError as err:
            _LOGGER.error(
                "Authentication error occurred during update: %s", err.response.text)
            raise ConfigEntryAuthFailed from err
        except GarminConnectTooManyRequestsError as err:
            _LOGGER.error(
                "Too many request error occurred during update: %s", err)
            return False
        except GarminConnectConnectionError as err:
            _LOGGER.error(
                "Connection error occurred during update: %s", err)
            raise ConfigEntryNotReady from err
        except requests.exceptions.HTTPError as err:
            if err.response.status_code == 401:
                _LOGGER.error(
                    "Authentication error occurred during update: %s", err.response.text)
                raise ConfigEntryAuthFailed from err
            if err.response.status_code == 429:
                _LOGGER.error(
                    "Too many requests error occurred during update: %s", err.response.text)
                return False
            _LOGGER.error(
                "Unknown HTTP error occurred during update: %s", err)
            return False
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.exception(
                "Unknown error occurred during update: %s", err)
            return False

        try:
            # Gear data like shoes, bike, etc.
            gear = await self.hass.async_add_executor_job(
                self.api.get_gear, summary[Gear.USERPROFILE_ID]
            )
            if gear:
                _LOGGER.debug("Gear data fetched: %s", gear)
            else:
                _LOGGER.debug("No gear data found")

            # Gear stats data like distance, time, etc.
            tasks: list[Awaitable] = [
                self.hass.async_add_executor_job(
                    self.api.get_gear_stats, gear_item[Gear.UUID])
                for gear_item in gear
            ]
            gear_stats = await asyncio.gather(*tasks)
            if gear_stats:
                _LOGGER.debug("Gear statistics data fetched: %s", gear_stats)
            else:
                _LOGGER.debug("No gear statistics data found")

            # Gear defaults data like shoe, bike, etc.
            gear_defaults = await self.hass.async_add_executor_job(
                self.api.get_gear_defaults, summary[Gear.USERPROFILE_ID]
            )
            if gear_defaults:
                _LOGGER.debug("Gear defaults data fetched: %s", gear_defaults)
            else:
                _LOGGER.debug("No gear defaults data found")
        except GarminConnectAuthenticationError as err:
            _LOGGER.error(
                "Authentication error occurred while fetching Gear data: %s", err.response.text)
            raise ConfigEntryAuthFailed from err
        except GarminConnectTooManyRequestsError as err:
            _LOGGER.error(
                "Too many request error occurred while fetching Gear data: %s", err)
            raise ConfigEntryNotReady from err
        except GarminConnectConnectionError as err:
            _LOGGER.error(
                "Connection error occurred while fetching Gear data: %s", err)
            raise ConfigEntryNotReady from err
        except requests.exceptions.HTTPError as err:
            if err.response.status_code == 401:
                _LOGGER.error(
                    "Authentication error while fetching Gear data: %s", err.response.text)
            elif err.response.status_code == 404:
                _LOGGER.error(
                    "URL not found error while fetching Gear data: %s", err.response.text)
            elif err.response.status_code == 429:
                _LOGGER.error(
                    "Too many requests error while fetching Gear data: %s", err.response.text)
            else:
                _LOGGER.error(
                    "Unknown HTTP error occurred while fetching Gear data: %s", err)
        except (KeyError, TypeError, ValueError, ConnectionError) as err:
            _LOGGER.debug("Error occurred while fetching Gear data: %s", err)

        # Sleep score data
        try:
            sleep_score = sleep_data["dailySleepDTO"]["sleepScores"]["overall"]["value"]
            _LOGGER.debug("Sleep score data: %s", sleep_score)
        except KeyError:
            _LOGGER.debug("No sleep score data found")

        # Sleep time seconds data
        try:
            sleep_time_seconds = sleep_data["dailySleepDTO"]["sleepTimeSeconds"]
            if sleep_time_seconds:
                _LOGGER.debug("Sleep time seconds data: %s",
                              sleep_time_seconds)
            else:
                _LOGGER.debug("No sleep time seconds data found")
        except KeyError:
            _LOGGER.debug("No sleep time seconds data found")

        # HRV data
        try:
            if hrv_data and "hrvSummary" in hrv_data:
                hrv_status = hrv_data["hrvSummary"]
                _LOGGER.debug("HRV summary status: %s", hrv_status)
        except KeyError:
            _LOGGER.debug(
                "Error occurred while processing HRV summary status data")

        return {
            **summary,
            **body["totalAverage"],
            "nextAlarm": next_alarms,
            "gear": gear,
            "gearStats": gear_stats,
            "activityTypes": activity_types,
            "gearDefaults": gear_defaults,
            "sleepScore": sleep_score,
            "sleepTimeSeconds": sleep_time_seconds,
            "hrvStatus": hrv_status,
            **fitnessage_data,
            **hydration_data,
        }


def calculate_next_active_alarms(alarms, time_zone):
    """
    Calculate garmin next active alarms from settings.
    Alarms are sorted by time.

    Example of alarms data:
    Alarms data fetched: [{'alarmMode': 'OFF', 'alarmTime': 1233, 'alarmDays': ['ONCE'], 'alarmSound': 'TONE_AND_VIBRATION', 'alarmId': 1737308355, 'changeState': 'UNCHANGED', 'backlight': 'ON', 'enabled': None, 'alarmMessage': None, 'alarmImageId': None, 'alarmIcon': None, 'alarmType': None}]
    """
    active_alarms = []

    if not alarms:
        return active_alarms

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
                alarm = start_of_week + \
                    timedelta(minutes=alarm_time, days=days_to_add)
                _LOGGER.debug("Start of week: %s, Alarm: %s",
                              start_of_week, alarm)

                # If the alarm time is in the past, move it to the next week
                if alarm < now:
                    alarm += timedelta(days=7)

            active_alarms.append(alarm.isoformat())

    return sorted(active_alarms) if active_alarms else None

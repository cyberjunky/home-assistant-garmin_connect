"""DataUpdateCoordinator for Garmin Connect integration."""

import asyncio
import logging
from collections.abc import Awaitable
from datetime import datetime, timedelta
from typing import Any
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
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DAY_TO_NUMBER,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    LEVEL_POINTS,
    Gear,
)

_LOGGER = logging.getLogger(__name__)


class GarminConnectDataUpdateCoordinator(DataUpdateCoordinator):
    """Garmin Connect Data Update Coordinator."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.entry = entry
        self.hass = hass
        self._in_china = hass.config.country == "CN"
        self.time_zone = hass.config.time_zone
        self.api = Garmin(is_cn=self._in_china)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_UPDATE_INTERVAL,
            config_entry=entry,
        )

    async def async_login(self) -> bool:
        """Authenticate with Garmin Connect using stored token."""
        try:
            if CONF_TOKEN not in self.entry.data:
                raise ConfigEntryAuthFailed(
                    "Token not found in config entry. Please reauthenticate."
                )

            await self.hass.async_add_executor_job(
                self.api.login, self.entry.data[CONF_TOKEN]
            )
        except ConfigEntryAuthFailed:
            raise
        except GarminConnectAuthenticationError as err:
            _LOGGER.error("Authentication error: %s", err.response.text)
            raise ConfigEntryAuthFailed from err
        except GarminConnectTooManyRequestsError as err:
            _LOGGER.error("Too many requests during login: %s", err)
            return False
        except GarminConnectConnectionError as err:
            _LOGGER.error("Connection error during login: %s", err)
            raise ConfigEntryNotReady from err
        except requests.exceptions.HTTPError as err:
            if err.response.status_code == 401:
                raise ConfigEntryAuthFailed from err
            if err.response.status_code == 429:
                _LOGGER.error("Too many requests: %s", err.response.text)
                return False
            _LOGGER.error("HTTP error during login: %s", err)
            return False
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.exception("Unknown error during login: %s", err)
            return False

        return True

    async def _async_update_data(self) -> dict:
        """Fetch data from Garmin Connect."""
        summary = {}
        body = {}
        alarms = {}
        gear = {}
        gear_stats: list[Any] = []
        gear_defaults = {}
        activity_types = {}
        last_activities = []
        sleep_data = {}
        sleep_score = None
        sleep_time_seconds = None
        hrv_data = {}
        hrv_status = {"status": "unknown"}
        endurance_data = {}
        endurance_status = {"overallScore": None}
        next_alarms: list[str] | None = []

        today = datetime.now(ZoneInfo(self.time_zone)).date()

        try:
            summary = await self.hass.async_add_executor_job(
                self.api.get_user_summary, today.isoformat()
            )

            body = await self.hass.async_add_executor_job(
                self.api.get_body_composition, today.isoformat()
            )

            last_activities = await self.hass.async_add_executor_job(
                self.api.get_activities_by_date,
                (today - timedelta(days=7)).isoformat(),
                (today + timedelta(days=1)).isoformat(),
            )

            summary["lastActivities"] = last_activities
            summary["lastActivity"] = last_activities[0] if last_activities else {}

            badges = await self.hass.async_add_executor_job(self.api.get_earned_badges)
            summary["badges"] = badges

            user_points = sum(
                badge["badgePoints"] * badge["badgeEarnedNumber"] for badge in badges
            )
            summary["userPoints"] = user_points

            user_level = 0
            for level, points in LEVEL_POINTS.items():
                if user_points >= points:
                    user_level = level
            summary["userLevel"] = user_level

            alarms = await self.hass.async_add_executor_job(self.api.get_device_alarms)
            next_alarms = calculate_next_active_alarms(alarms, self.time_zone)

            activity_types = await self.hass.async_add_executor_job(
                self.api.get_activity_types
            )

            sleep_data = await self.hass.async_add_executor_job(
                self.api.get_sleep_data, today.isoformat()
            )

            hrv_data = await self.hass.async_add_executor_job(
                self.api.get_hrv_data, today.isoformat()
            )

            endurance_data = await self.hass.async_add_executor_job(
                self.api.get_endurance_score, today.isoformat()
            )

        except (
            GarminConnectAuthenticationError,
            GarminConnectTooManyRequestsError,
            GarminConnectConnectionError,
        ) as error:
            _LOGGER.debug("Trying to relogin to Garmin Connect")
            if not await self.async_login():
                raise UpdateFailed(error) from error

        try:
            if Gear.USERPROFILE_ID in summary:
                gear = await self.hass.async_add_executor_job(
                    self.api.get_gear, summary[Gear.USERPROFILE_ID]
                )

            fitnessage_data = await self.hass.async_add_executor_job(
                self.api.get_fitnessage_data, today.isoformat()
            )

            hydration_data = await self.hass.async_add_executor_job(
                self.api.get_hydration_data, today.isoformat()
            )

        except GarminConnectAuthenticationError as err:
            raise ConfigEntryAuthFailed from err
        except GarminConnectTooManyRequestsError:
            return {}
        except GarminConnectConnectionError as err:
            raise ConfigEntryNotReady from err
        except requests.exceptions.HTTPError as err:
            if err.response.status_code == 401:
                raise ConfigEntryAuthFailed from err
            if err.response.status_code == 429:
                return {}
            _LOGGER.error("HTTP error during update: %s", err)
            return {}
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.exception("Unknown error during update: %s", err)
            return {}

        try:
            if gear:
                tasks: list[Awaitable] = [
                    self.hass.async_add_executor_job(
                        self.api.get_gear_stats, gear_item[Gear.UUID]
                    )
                    for gear_item in gear
                ]
                gear_stats = await asyncio.gather(*tasks)

                if Gear.USERPROFILE_ID in summary:
                    gear_defaults = await self.hass.async_add_executor_job(
                        self.api.get_gear_defaults, summary[Gear.USERPROFILE_ID]
                    )
        except GarminConnectAuthenticationError as err:
            raise ConfigEntryAuthFailed from err
        except GarminConnectTooManyRequestsError as err:
            raise ConfigEntryNotReady from err
        except GarminConnectConnectionError as err:
            raise ConfigEntryNotReady from err
        except requests.exceptions.HTTPError:
            pass
        except (KeyError, TypeError, ValueError, ConnectionError) as err:
            _LOGGER.debug("Error fetching gear data: %s", err)

        try:
            sleep_score = sleep_data["dailySleepDTO"]["sleepScores"]["overall"]["value"]
        except KeyError:
            pass

        try:
            sleep_time_seconds = sleep_data["dailySleepDTO"]["sleepTimeSeconds"]
        except KeyError:
            pass

        try:
            if hrv_data and "hrvSummary" in hrv_data:
                hrv_status = hrv_data["hrvSummary"]
        except KeyError:
            pass

        try:
            if endurance_data and "overallScore" in endurance_data:
                endurance_status = endurance_data
        except KeyError:
            pass

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
            "enduranceScore": endurance_status,
            **fitnessage_data,
            **hydration_data,
        }


def calculate_next_active_alarms(alarms: Any, time_zone: str) -> list[str] | None:
    """Calculate the next scheduled active alarms."""
    active_alarms: list[str] = []

    if not alarms:
        return active_alarms

    now = datetime.now(ZoneInfo(time_zone))

    for alarm_setting in alarms:
        if alarm_setting["alarmMode"] != "ON":
            continue

        for day in alarm_setting["alarmDays"]:
            alarm_time = alarm_setting["alarmTime"]
            if day == "ONCE":
                midnight = datetime.combine(
                    now.date(), datetime.min.time(), tzinfo=ZoneInfo(time_zone)
                )
                alarm = midnight + timedelta(minutes=alarm_time)
                if alarm < now:
                    alarm += timedelta(days=1)
            else:
                start_of_week = datetime.combine(
                    now.date() - timedelta(days=now.date().isoweekday() - 1),
                    datetime.min.time(),
                    tzinfo=ZoneInfo(time_zone),
                )
                alarm = start_of_week + timedelta(
                    days=DAY_TO_NUMBER[day] - 1, minutes=alarm_time
                )
                if alarm < now:
                    alarm += timedelta(days=7)

            active_alarms.append(alarm.isoformat())

    return sorted(active_alarms) if active_alarms else None

"""DataUpdateCoordinators for Garmin Connect.

Multiple coordinators allow users to disable entity groups and stop unnecessary API calls.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from aiohttp import ClientError
from ha_garmin import GarminAuth, GarminClient
from ha_garmin.exceptions import GarminAuthError, GarminConnectError
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_CLIENT_ID,
    CONF_REFRESH_TOKEN,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

# Consecutive empty *calendar days* (not poll cycles - fetch_nutrition_data() always
# queries "today", so multiple same-day polls must not each count) before raising a
# "Connect+ required" repair issue. fetch_nutrition_data() returns {} both when the
# account lacks Connect+ and on transient API errors, so we require a run of empty days
# to rule out a one-off blip. The issue is never raised (and never re-raised) once any
# poll has ever returned real data, since that proves the account IS set up correctly -
# a later gap just means the user hasn't logged food, not that Connect+ is missing.
_NUTRITION_EMPTY_DAY_THRESHOLD = 3


@dataclass
class GarminConnectCoordinators:
    """Container for all Garmin Connect coordinators."""

    core: CoreCoordinator
    activity: ActivityCoordinator
    training: TrainingCoordinator
    body: BodyCoordinator
    goals: GoalsCoordinator
    gear: GearCoordinator
    blood_pressure: BloodPressureCoordinator
    menstrual: MenstrualCoordinator
    nutrition: NutritionCoordinator
    is_cn: bool = False
    """China region the client was built for; a change needs a reload."""

    def __iter__(self):
        """Iterate over the coordinators."""
        yield from (
            self.core,
            self.activity,
            self.training,
            self.body,
            self.goals,
            self.gear,
            self.blood_pressure,
            self.menstrual,
            self.nutrition,
        )


class BaseGarminCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Base class for Garmin Connect coordinators.

    Subclasses only name their data domain and implement ``_fetch``; error
    mapping and token persistence live here.
    """

    config_entry: ConfigEntry
    data_name: str

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: GarminClient,
        auth: GarminAuth,
    ) -> None:
        """Initialize."""
        scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{self.data_name}",
            update_interval=timedelta(seconds=scan_interval),
        )
        self.client = client
        self.auth = auth

    def set_update_interval(self, update_interval: timedelta) -> None:
        """Update the coordinator's polling interval."""
        self.update_interval = update_interval

    async def _fetch(self) -> dict[str, Any]:
        """Fetch this coordinator's data from Garmin Connect."""
        raise NotImplementedError

    @callback
    def _update_tokens_if_changed(self) -> None:
        """Persist tokens if the library rotated them during a request.

        Runs after every poll, successful or not: a token refresh can
        succeed and the data request still fail, and the new refresh token
        would otherwise be lost on restart. Tokens wiped by a failed
        login are not persisted; reauth replaces them.
        """
        if not self.auth.di_token or not self.auth.di_refresh_token:
            return
        if (
            self.auth.di_token != self.config_entry.data.get(CONF_TOKEN)
            or self.auth.di_refresh_token != self.config_entry.data.get(CONF_REFRESH_TOKEN)
            or self.auth.di_client_id != self.config_entry.data.get(CONF_CLIENT_ID)
        ):
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={
                    **self.config_entry.data,
                    CONF_TOKEN: self.auth.di_token,
                    CONF_REFRESH_TOKEN: self.auth.di_refresh_token,
                    CONF_CLIENT_ID: self.auth.di_client_id,
                },
            )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data, mapping library errors to coordinator errors."""
        try:
            return await self._fetch()
        except GarminAuthError as err:
            raise ConfigEntryAuthFailed("Authentication failed") from err
        except (GarminConnectError, ClientError) as err:
            _LOGGER.debug("Error fetching %s data: %s", self.data_name, err)
            raise UpdateFailed(f"Error fetching {self.data_name} data: {err}") from err
        finally:
            self._update_tokens_if_changed()


class CoreCoordinator(BaseGarminCoordinator):
    """Coordinator for core data: summary, steps, sleep (~50 sensors)."""

    data_name = "core"

    async def _fetch(self) -> dict[str, Any]:
        """Fetch core data."""
        return await self.client.fetch_core_data()


class ActivityCoordinator(BaseGarminCoordinator):
    """Coordinator for activity data: activities, workouts (~8 sensors)."""

    data_name = "activity"

    async def _fetch(self) -> dict[str, Any]:
        """Fetch activity data."""
        return await self.client.fetch_activity_data()


class TrainingCoordinator(BaseGarminCoordinator):
    """Coordinator for training data: readiness, status, scores, HRV (~14 sensors)."""

    data_name = "training"

    async def _fetch(self) -> dict[str, Any]:
        """Fetch training data."""
        return await self.client.fetch_training_data()


class BodyCoordinator(BaseGarminCoordinator):
    """Coordinator for body data: weight, hydration, fitness age (~18 sensors)."""

    data_name = "body"

    async def _fetch(self) -> dict[str, Any]:
        """Fetch body data."""
        return await self.client.fetch_body_data()


class GoalsCoordinator(BaseGarminCoordinator):
    """Coordinator for goals data: goals, badges, points (~6 sensors)."""

    data_name = "goals"

    async def _fetch(self) -> dict[str, Any]:
        """Fetch goals data."""
        return await self.client.fetch_goals_data()


class GearCoordinator(BaseGarminCoordinator):
    """Coordinator for gear data: gear, devices, alarms (static + dynamic sensors)."""

    data_name = "gear"

    async def _fetch(self) -> dict[str, Any]:
        """Fetch gear data; alarms are resolved in the Home Assistant time zone."""
        return await self.client.fetch_gear_data(timezone=self.hass.config.time_zone)


class BloodPressureCoordinator(BaseGarminCoordinator):
    """Coordinator for blood pressure data (~4 sensors)."""

    data_name = "blood_pressure"

    async def _fetch(self) -> dict[str, Any]:
        """Fetch blood pressure data."""
        return await self.client.fetch_blood_pressure_data()


class MenstrualCoordinator(BaseGarminCoordinator):
    """Coordinator for menstrual data (~9 sensors, disabled by default)."""

    data_name = "menstrual"

    async def _fetch(self) -> dict[str, Any]:
        """Fetch menstrual data."""
        return await self.client.fetch_menstrual_data()


class NutritionCoordinator(BaseGarminCoordinator):
    """Coordinator for nutrition log data (~11 sensors, disabled by default, Connect+)."""

    data_name = "nutrition"

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: GarminClient,
        auth: GarminAuth,
    ) -> None:
        """Initialize."""
        super().__init__(hass, entry, client, auth)
        self._ever_had_data = False
        self._empty_days = 0
        self._last_empty_date: date | None = None

    async def _fetch(self) -> dict[str, Any]:
        """Fetch nutrition data."""
        return await self.client.fetch_nutrition_data()

    @property
    def _connect_plus_issue_id(self) -> str:
        return f"nutrition_connect_plus_required_{self.config_entry.entry_id}"

    def _has_enabled_nutrition_entity(self) -> bool:
        """Return True if the user has enabled at least one nutrition sensor.

        Nutrition sensors are disabled by default and this coordinator polls
        unconditionally regardless of that, so most installs never touch the
        feature at all. An empty response is only worth surfacing if the user
        has actually opted in by enabling a nutrition sensor.
        """
        registry = er.async_get(self.hass)
        prefix = f"{self.config_entry.entry_id}_nutrition"
        return any(
            entry.unique_id.startswith(prefix) and entry.disabled_by is None
            for entry in er.async_entries_for_config_entry(registry, self.config_entry.entry_id)
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch nutrition data and track empty days for the Connect+ repair issue."""
        data = await super()._async_update_data()

        if data:
            # Any real data proves Connect+/nutrition is set up - never warn again,
            # even if the user later goes days without logging food.
            self._ever_had_data = True
            self._empty_days = 0
            self._last_empty_date = None
            ir.async_delete_issue(self.hass, DOMAIN, self._connect_plus_issue_id)
        elif self._ever_had_data:
            pass  # A later gap just means no food was logged, not a missing subscription.
        elif not self._has_enabled_nutrition_entity():
            # Feature not opted into - never nag, and start a fresh debounce window
            # if the user enables it later.
            self._empty_days = 0
            self._last_empty_date = None
            ir.async_delete_issue(self.hass, DOMAIN, self._connect_plus_issue_id)
        else:
            today = dt_util.now().date()
            if today != self._last_empty_date:
                self._last_empty_date = today
                self._empty_days += 1
                if self._empty_days == _NUTRITION_EMPTY_DAY_THRESHOLD:
                    ir.async_create_issue(
                        self.hass,
                        DOMAIN,
                        self._connect_plus_issue_id,
                        is_fixable=False,
                        severity=ir.IssueSeverity.WARNING,
                        translation_key="connect_plus_required",
                        translation_placeholders={"title": self.config_entry.title},
                    )
        return data


type GarminConnectConfigEntry = ConfigEntry[GarminConnectCoordinators]

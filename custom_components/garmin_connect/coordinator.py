"""DataUpdateCoordinators for Garmin Connect.

Multiple coordinators allow users to disable entity groups and stop unnecessary API calls.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from aiohttp import ClientError
from ha_garmin import GarminAuth, GarminClient
from ha_garmin.exceptions import GarminAuthError, GarminConnectError
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
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


class BaseGarminCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Base class for Garmin Connect coordinators."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: GarminClient,
        auth: GarminAuth,
        name: str,
        update_interval: timedelta,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{name}",
            update_interval=update_interval,
        )
        self.client = client
        self.auth = auth
        self._refresh_lock = asyncio.Lock()

    def set_update_interval(self, update_interval: timedelta) -> None:
        """Update the coordinator's polling interval."""
        self.update_interval = update_interval

    async def _update_tokens_if_changed(self) -> None:
        """Update stored tokens if they changed during refresh."""
        async with self._refresh_lock:
            if (
                self.auth.di_token != self.config_entry.data[CONF_TOKEN]
                or self.auth.di_refresh_token != self.config_entry.data[CONF_REFRESH_TOKEN]
                or self.auth.di_client_id != self.config_entry.data[CONF_CLIENT_ID]
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


class CoreCoordinator(BaseGarminCoordinator):
    """Coordinator for core data: summary, steps, sleep (~50 sensors)."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: GarminClient,
        auth: GarminAuth,
    ) -> None:
        """Initialize."""
        scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(hass, entry, client, auth, "core", timedelta(seconds=scan_interval))

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch core data from Garmin Connect."""
        try:
            data = await self.client.fetch_core_data()
            await self._update_tokens_if_changed()
        except GarminAuthError as err:
            raise ConfigEntryAuthFailed("Authentication failed") from err
        except (GarminConnectError, ClientError) as err:
            _LOGGER.debug("Error fetching core data: %s", err)
            raise UpdateFailed(f"Error fetching core data: {err}") from err
        return data


class ActivityCoordinator(BaseGarminCoordinator):
    """Coordinator for activity data: activities, workouts (~4 sensors)."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: GarminClient,
        auth: GarminAuth,
    ) -> None:
        """Initialize."""
        scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(hass, entry, client, auth, "activity", timedelta(seconds=scan_interval))

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch activity data from Garmin Connect."""
        try:
            data = await self.client.fetch_activity_data()
            await self._update_tokens_if_changed()
        except GarminAuthError as err:
            raise ConfigEntryAuthFailed("Authentication failed") from err
        except (GarminConnectError, ClientError) as err:
            _LOGGER.debug("Error fetching activity data: %s", err)
            raise UpdateFailed(f"Error fetching activity data: {err}") from err
        return data


class TrainingCoordinator(BaseGarminCoordinator):
    """Coordinator for training data: readiness, status, scores, HRV (~11 sensors)."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: GarminClient,
        auth: GarminAuth,
    ) -> None:
        """Initialize."""
        scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(hass, entry, client, auth, "training", timedelta(seconds=scan_interval))

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch training data from Garmin Connect."""
        try:
            data = await self.client.fetch_training_data()
            await self._update_tokens_if_changed()
        except GarminAuthError as err:
            raise ConfigEntryAuthFailed("Authentication failed") from err
        except (GarminConnectError, ClientError) as err:
            _LOGGER.debug("Error fetching training data: %s", err)
            raise UpdateFailed(f"Error fetching training data: {err}") from err
        return data


class BodyCoordinator(BaseGarminCoordinator):
    """Coordinator for body data: weight, hydration, fitness age (~17 sensors)."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: GarminClient,
        auth: GarminAuth,
    ) -> None:
        """Initialize."""
        scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(hass, entry, client, auth, "body", timedelta(seconds=scan_interval))

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch body data from Garmin Connect."""
        try:
            data = await self.client.fetch_body_data()
            await self._update_tokens_if_changed()
        except GarminAuthError as err:
            raise ConfigEntryAuthFailed("Authentication failed") from err
        except (GarminConnectError, ClientError) as err:
            _LOGGER.debug("Error fetching body data: %s", err)
            raise UpdateFailed(f"Error fetching body data: {err}") from err
        return data


class GoalsCoordinator(BaseGarminCoordinator):
    """Coordinator for goals data: goals, badges, points (~6 sensors)."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: GarminClient,
        auth: GarminAuth,
    ) -> None:
        """Initialize."""
        scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(hass, entry, client, auth, "goals", timedelta(seconds=scan_interval))

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch goals data from Garmin Connect."""
        try:
            data = await self.client.fetch_goals_data()
            await self._update_tokens_if_changed()
        except GarminAuthError as err:
            raise ConfigEntryAuthFailed("Authentication failed") from err
        except (GarminConnectError, ClientError) as err:
            _LOGGER.debug("Error fetching goals data: %s", err)
            raise UpdateFailed(f"Error fetching goals data: {err}") from err
        return data


class GearCoordinator(BaseGarminCoordinator):
    """Coordinator for gear data: gear, alarms (1 static + dynamic sensors)."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: GarminClient,
        auth: GarminAuth,
    ) -> None:
        """Initialize."""
        scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(hass, entry, client, auth, "gear", timedelta(seconds=scan_interval))

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch gear data from Garmin Connect."""
        try:
            data = await self.client.fetch_gear_data(timezone=self.hass.config.time_zone)
            await self._update_tokens_if_changed()
        except GarminAuthError as err:
            raise ConfigEntryAuthFailed("Authentication failed") from err
        except (GarminConnectError, ClientError) as err:
            _LOGGER.debug("Error fetching gear data: %s", err)
            raise UpdateFailed(f"Error fetching gear data: {err}") from err
        return data


class BloodPressureCoordinator(BaseGarminCoordinator):
    """Coordinator for blood pressure data (~3 sensors)."""

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
            entry,
            client,
            auth,
            "blood_pressure",
            timedelta(seconds=scan_interval),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch blood pressure data from Garmin Connect."""
        try:
            data = await self.client.fetch_blood_pressure_data()
            await self._update_tokens_if_changed()
        except GarminAuthError as err:
            raise ConfigEntryAuthFailed("Authentication failed") from err
        except (GarminConnectError, ClientError) as err:
            _LOGGER.debug("Error fetching blood pressure data: %s", err)
            raise UpdateFailed(f"Error fetching blood pressure data: {err}") from err
        return data


class MenstrualCoordinator(BaseGarminCoordinator):
    """Coordinator for menstrual data (~9 sensors, disabled by default)."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: GarminClient,
        auth: GarminAuth,
    ) -> None:
        """Initialize."""
        scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(hass, entry, client, auth, "menstrual", timedelta(seconds=scan_interval))

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch menstrual data from Garmin Connect."""
        try:
            data = await self.client.fetch_menstrual_data()
            await self._update_tokens_if_changed()
        except GarminAuthError as err:
            raise ConfigEntryAuthFailed("Authentication failed") from err
        except (GarminConnectError, ClientError) as err:
            _LOGGER.debug("Error fetching menstrual data: %s", err)
            raise UpdateFailed(f"Error fetching menstrual data: {err}") from err
        return data


class NutritionCoordinator(BaseGarminCoordinator):
    """Coordinator for nutrition log data (~11 sensors, disabled by default, Connect+)."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: GarminClient,
        auth: GarminAuth,
    ) -> None:
        """Initialize."""
        scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(hass, entry, client, auth, "nutrition", timedelta(seconds=scan_interval))
        self._ever_had_data = False
        self._empty_days = 0
        self._last_empty_date: date | None = None

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
        """Fetch nutrition data from Garmin Connect."""
        try:
            data = await self.client.fetch_nutrition_data()
            await self._update_tokens_if_changed()
        except GarminAuthError as err:
            raise ConfigEntryAuthFailed("Authentication failed") from err
        except (GarminConnectError, ClientError) as err:
            _LOGGER.debug("Error fetching nutrition data: %s", err)
            raise UpdateFailed(f"Error fetching nutrition data: {err}") from err

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

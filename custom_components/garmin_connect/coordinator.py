"""DataUpdateCoordinators for Garmin Connect.

Multiple coordinators allow users to disable entity groups and stop unnecessary API calls.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from ha_garmin import GarminAuth, GarminClient
from ha_garmin.exceptions import GarminAPIError, GarminAuthError
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_CLIENT_ID,
    CONF_REFRESH_TOKEN,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


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

    async def _update_tokens_if_changed(self) -> None:
        """Update stored tokens if they changed during refresh."""
        async with self._refresh_lock:
            if (
                self.auth.di_token != self.config_entry.data[CONF_TOKEN]
                or self.auth.di_refresh_token
                != self.config_entry.data[CONF_REFRESH_TOKEN]
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
        super().__init__(
            hass, entry, client, auth, "core", timedelta(seconds=scan_interval)
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch core data from Garmin Connect."""
        try:
            data = await self.client.fetch_core_data()
            await self._update_tokens_if_changed()
        except GarminAuthError as err:
            raise ConfigEntryAuthFailed("Authentication failed") from err
        except Exception as err:
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
        super().__init__(
            hass, entry, client, auth, "activity", timedelta(seconds=scan_interval)
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch activity data from Garmin Connect."""
        try:
            data = await self.client.fetch_activity_data()
            await self._update_tokens_if_changed()
        except GarminAuthError as err:
            raise ConfigEntryAuthFailed("Authentication failed") from err
        except GarminAPIError as err:
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
        super().__init__(
            hass, entry, client, auth, "training", timedelta(seconds=scan_interval)
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch training data from Garmin Connect."""
        try:
            data = await self.client.fetch_training_data()
            await self._update_tokens_if_changed()
        except GarminAuthError as err:
            raise ConfigEntryAuthFailed("Authentication failed") from err
        except GarminAPIError as err:
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
        super().__init__(
            hass, entry, client, auth, "body", timedelta(seconds=scan_interval)
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch body data from Garmin Connect."""
        try:
            data = await self.client.fetch_body_data()
            await self._update_tokens_if_changed()
        except GarminAuthError as err:
            raise ConfigEntryAuthFailed("Authentication failed") from err
        except GarminAPIError as err:
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
        super().__init__(
            hass, entry, client, auth, "goals", timedelta(seconds=scan_interval)
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch goals data from Garmin Connect."""
        try:
            data = await self.client.fetch_goals_data()
            await self._update_tokens_if_changed()
        except GarminAuthError as err:
            raise ConfigEntryAuthFailed("Authentication failed") from err
        except GarminAPIError as err:
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
        super().__init__(
            hass, entry, client, auth, "gear", timedelta(seconds=scan_interval)
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch gear data from Garmin Connect."""
        try:
            data = await self.client.fetch_gear_data(
                timezone=self.hass.config.time_zone
            )
            await self._update_tokens_if_changed()
        except GarminAuthError as err:
            raise ConfigEntryAuthFailed("Authentication failed") from err
        except GarminAPIError as err:
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
        except GarminAPIError as err:
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
        super().__init__(
            hass, entry, client, auth, "menstrual", timedelta(seconds=scan_interval)
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch menstrual data from Garmin Connect."""
        try:
            data = await self.client.fetch_menstrual_data()
            await self._update_tokens_if_changed()
        except GarminAuthError as err:
            raise ConfigEntryAuthFailed("Authentication failed") from err
        except GarminAPIError as err:
            raise UpdateFailed(f"Error fetching menstrual data: {err}") from err
        return data


type GarminConnectConfigEntry = ConfigEntry[GarminConnectCoordinators]

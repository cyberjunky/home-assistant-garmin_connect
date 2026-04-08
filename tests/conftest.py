"""Fixtures for Garmin Connect tests."""

from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.garmin_connect.const import (
    CONF_CLIENT_ID,
    CONF_REFRESH_TOKEN,
    CONF_TOKEN,
    DOMAIN,
)


@pytest.fixture
def mock_config_entry() -> MagicMock:
    """Return a mock config entry."""
    entry = MagicMock()
    entry.domain = DOMAIN
    entry.title = "test@example.com"
    entry.data = {
        CONF_TOKEN: "mock_di_token.eyJleHAiOjk5OTk5OTk5OTl9.sig",
        CONF_REFRESH_TOKEN: "mock_di_refresh_token",
        CONF_CLIENT_ID: "GARMIN_CONNECT_MOBILE_ANDROID_DI",
    }
    entry.unique_id = "test@example.com"
    entry.entry_id = "test_entry_id"
    return entry


@pytest.fixture
def mock_auth() -> Generator[MagicMock]:
    """Return a mock GarminAuth."""
    with patch(
        "custom_components.garmin_connect.GarminAuth",
        autospec=True,
    ) as mock_cls:
        auth = mock_cls.return_value
        auth.di_token = "mock_di_token.eyJleHAiOjk5OTk5OTk5OTl9.sig"
        auth.di_refresh_token = "mock_di_refresh_token"
        auth.di_client_id = "GARMIN_CONNECT_MOBILE_ANDROID_DI"
        auth.is_authenticated = True
        yield auth


@pytest.fixture
def mock_client() -> Generator[MagicMock]:
    """Return a mock GarminClient."""
    with patch(
        "custom_components.garmin_connect.GarminClient",
        autospec=True,
    ) as mock_cls:
        client = mock_cls.return_value
        client.fetch_core_data = AsyncMock(return_value=_mock_sensor_data())
        yield client


@pytest.fixture
def mock_sensor_data() -> dict:
    """Return mock sensor data for the core coordinator."""
    return _mock_sensor_data()


def _mock_sensor_data() -> dict:
    """Build mock sensor data dict."""
    return {
        "totalSteps": 10000,
        "totalDistanceMeters": 8000.0,
        "activeKilocalories": 500,
        "restingHeartRate": 60,
        "minHeartRate": 50,
        "maxHeartRate": 150,
        "averageStressLevel": 30,
        "bodyBatteryMostRecentValue": 80,
        "bodyBatteryChargedValue": 40,
        "bodyBatteryDrainedValue": 20,
        "floorsAscended": 10,
        "floorsDescended": 5,
        "dailyStepGoal": 10000,
        "sleepingMinutes": 480,
        "deepSleepMinutes": 120,
        "lightSleepMinutes": 240,
        "remSleepMinutes": 120,
        "lastSyncTimestamp": datetime(2026, 1, 24, 12, 0, 0, tzinfo=UTC),
        "latestSpo2ReadingTime": datetime(2026, 1, 24, 5, 30, 0, tzinfo=UTC),
        "latestRespirationTime": datetime(2026, 1, 24, 11, 0, 0, tzinfo=UTC),
        "wellnessStartTime": datetime(2026, 1, 23, 23, 0, 0, tzinfo=UTC),
        "wellnessEndTime": datetime(2026, 1, 24, 16, 0, 0, tzinfo=UTC),
    }

"""Shared fixtures for Garmin Connect integration tests."""

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_api():
    """Create a mock Garmin Connect API client."""
    api = MagicMock()
    api.add_hydration_data = MagicMock()
    api.add_body_composition = MagicMock()
    api.set_blood_pressure = MagicMock()
    return api


@pytest.fixture
def mock_coordinator(mock_api):
    """Create a mock coordinator with a working API and login."""
    coordinator = MagicMock()
    coordinator.api = mock_api
    coordinator.async_login = AsyncMock(return_value=True)
    coordinator.data = {
        "valueInML": 1500.0,
        "goalInML": 2500.0,
        "lastSyncTimestampGMT": "2026-03-15T12:00:00.0",
    }
    return coordinator


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock()

    async def async_add_executor_job(func, *args):
        return func(*args)

    hass.async_add_executor_job = async_add_executor_job
    return hass

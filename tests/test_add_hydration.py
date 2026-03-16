"""Tests for the add_hydration entity service."""

from unittest.mock import AsyncMock

import pytest
from homeassistant.exceptions import IntegrationError


@pytest.fixture
def hydration_sensor(mock_coordinator, mock_hass):
    """Create a GarminConnectSensor instance for hydration testing."""
    from custom_components.garmin_connect.sensor import GarminConnectSensor

    sensor = GarminConnectSensor.__new__(GarminConnectSensor)
    sensor.coordinator = mock_coordinator
    sensor.hass = mock_hass
    return sensor


class TestAddHydration:
    """Tests for the add_hydration service method."""

    async def test_add_hydration_required_params_only(self, hydration_sensor, mock_api):
        """Logging hydration with only value_in_ml calls the API correctly."""
        await hydration_sensor.add_hydration(value_in_ml=250.0)

        mock_api.add_hydration_data.assert_called_once_with(250.0, None)

    async def test_add_hydration_with_timestamp(self, hydration_sensor, mock_api):
        """Logging hydration with a timestamp passes it through to the API."""
        await hydration_sensor.add_hydration(
            value_in_ml=500.0,
            timestamp="2026-03-15T08:30:00.000",
        )

        mock_api.add_hydration_data.assert_called_once_with(
            500.0, "2026-03-15T08:30:00.000"
        )

    async def test_add_hydration_login_failure_raises(self, hydration_sensor, mock_coordinator):
        """When login fails, add_hydration raises IntegrationError."""
        mock_coordinator.async_login = AsyncMock(return_value=False)

        with pytest.raises(IntegrationError, match="Failed to login"):
            await hydration_sensor.add_hydration(value_in_ml=250.0)

        mock_coordinator.api.add_hydration_data.assert_not_called()

    async def test_add_hydration_negative_value(self, hydration_sensor, mock_api):
        """Negative values (subtracting intake) are passed through to the API."""
        await hydration_sensor.add_hydration(value_in_ml=-100.0)

        mock_api.add_hydration_data.assert_called_once_with(-100.0, None)

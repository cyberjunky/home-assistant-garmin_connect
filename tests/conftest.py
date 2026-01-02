"""Test fixtures for Garmin Connect integration."""

from unittest.mock import patch

import pytest


@pytest.fixture
def mock_garmin_client():
    """Mock Garmin Connect client."""
    with patch("custom_components.garmin_connect.coordinator.Garmin") as mock:
        mock_instance = mock.return_value
        mock_instance.login.return_value = None
        mock_instance.get_user_summary.return_value = {
            "totalSteps": 5000,
            "dailyStepGoal": 10000,
            "totalKilocalories": 2000,
            "lastSyncTimestampGMT": "2024-01-01T12:00:00",
            "userProfileId": "12345",
        }
        mock_instance.get_body_composition.return_value = {
            "totalAverage": {"weight": 75.0, "bmi": 24.5}
        }
        mock_instance.get_activities_by_date.return_value = []
        mock_instance.get_earned_badges.return_value = []
        mock_instance.get_device_alarms.return_value = []
        mock_instance.get_activity_types.return_value = []
        mock_instance.get_sleep_data.return_value = {}
        mock_instance.get_hrv_data.return_value = {}
        mock_instance.get_endurance_score.return_value = {}
        mock_instance.get_gear.return_value = []
        mock_instance.get_fitnessage_data.return_value = {}
        mock_instance.get_hydration_data.return_value = {}
        mock_instance.garth.dumps.return_value = "mock_token"
        yield mock_instance

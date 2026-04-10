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

ENTRY_DATA = {
    CONF_TOKEN: "mock_token.eyJleHAiOjk5OTk5OTk5OTl9.sig",
    CONF_REFRESH_TOKEN: "mock_refresh_token",
    CONF_CLIENT_ID: "GARMIN_CONNECT_MOBILE_ANDROID_DI",
}


@pytest.fixture
def mock_config_entry() -> MagicMock:
    """Return a mock config entry."""
    entry = MagicMock()
    entry.domain = DOMAIN
    entry.title = "test@example.com"
    entry.data = dict(ENTRY_DATA)
    entry.options = {}
    entry.unique_id = "123456789"
    entry.entry_id = "test_entry_id"
    return entry


@pytest.fixture
def mock_auth() -> Generator[MagicMock]:
    """Return a mock GarminAuth patched into the integration module."""
    with patch(
        "custom_components.garmin_connect.GarminAuth",
        autospec=True,
    ) as mock_cls:
        auth = mock_cls.return_value
        auth.di_token = ENTRY_DATA[CONF_TOKEN]
        auth.di_refresh_token = ENTRY_DATA[CONF_REFRESH_TOKEN]
        auth.di_client_id = ENTRY_DATA[CONF_CLIENT_ID]
        yield auth


@pytest.fixture
def mock_client() -> Generator[MagicMock]:
    """Return a mock GarminClient with all fetch methods stubbed."""
    with patch(
        "custom_components.garmin_connect.GarminClient",
        autospec=True,
    ) as mock_cls:
        client = mock_cls.return_value
        client.fetch_core_data = AsyncMock(return_value=mock_core_data())
        client.fetch_activity_data = AsyncMock(return_value=mock_activity_data())
        client.fetch_training_data = AsyncMock(return_value=mock_training_data())
        client.fetch_body_data = AsyncMock(return_value=mock_body_data())
        client.fetch_goals_data = AsyncMock(return_value=mock_goals_data())
        client.fetch_gear_data = AsyncMock(return_value=mock_gear_data())
        client.fetch_blood_pressure_data = AsyncMock(
            return_value=mock_blood_pressure_data()
        )
        client.fetch_menstrual_data = AsyncMock(return_value={})
        yield client


# ── Per-coordinator sample data ──────────────────────────────────────────────


def mock_core_data() -> dict:
    """Sample data for CoreCoordinator (fetch_core_data output)."""
    return {
        "totalSteps": 10000,
        "dailyStepGoal": 10000,
        "yesterdaySteps": 9500,
        "weeklyStepAvg": 8500,
        "totalDistanceMeters": 8000.0,
        "yesterdayDistance": 7500.0,
        "weeklyDistanceAvg": 7200.0,
        "floorsAscended": 10,
        "floorsDescended": 5,
        "userFloorsAscendedGoal": 10,
        "floorsAscendedInMeters": 30.0,
        "floorsDescendedInMeters": 15.0,
        "totalKilocalories": 2200,
        "activeKilocalories": 500,
        "bmrKilocalories": 1700,
        "burnedKilocalories": 1800,
        "consumedKilocalories": 2500,
        "remainingKilocalories": 700,
        "restingHeartRate": 60,
        "maxHeartRate": 150,
        "minHeartRate": 50,
        "lastSevenDaysAvgRestingHeartRate": 62,
        "minAvgHeartRate": 55,
        "maxAvgHeartRate": 145,
        "abnormalHeartRateAlertsCount": 0,
        "averageStressLevel": 30,
        "maxStressLevel": 75,
        "stressQualifierText": "calm",
        "stressMinutes": 360,
        "restStressMinutes": 180,
        "activityStressMinutes": 45,
        "lowStressMinutes": 90,
        "mediumStressMinutes": 30,
        "highStressMinutes": 15,
        "uncategorizedStressMinutes": 0,
        "stressPercentage": 50.0,
        "restStressPercentage": 25.0,
        "activityStressPercentage": 6.25,
        "uncategorizedStressPercentage": 0.0,
        "lowStressPercentage": 12.5,
        "mediumStressPercentage": 4.17,
        "highStressPercentage": 2.08,
        "sleepingMinutes": 480,
        "sleepTimeMinutes": 450,
        "measurableAsleepDurationMinutes": 430,
        "measurableAwakeDurationMinutes": 20,
        "sleepScore": 82,
        "deepSleepMinutes": 120,
        "lightSleepMinutes": 240,
        "remSleepMinutes": 120,
        "awakeSleepMinutes": 20,
        "napTimeMinutes": 0,
        "unmeasurableSleepMinutes": 0,
        "bodyBatteryMostRecentValue": 80,
        "bodyBatteryHighestValue": 95,
        "bodyBatteryLowestValue": 20,
        "bodyBatteryChargedValue": 40,
        "bodyBatteryDrainedValue": 20,
        "activeMinutes": 45,
        "highlyActiveMinutes": 20,
        "sedentaryMinutes": 500,
        "moderateIntensityMinutes": 25,
        "vigorousIntensityMinutes": 10,
        "intensityMinutesGoal": 150,
        "totalIntensityMinutes": 35,
        "averageSpo2": 97.0,
        "lowestSpo2": 93,
        "latestSpo2": 98,
        "latestSpo2ReadingTime": datetime(2026, 1, 24, 5, 30, 0, tzinfo=UTC),
        "highestRespirationValue": 18.0,
        "lowestRespirationValue": 12.0,
        "latestRespirationValue": 15.0,
        "latestRespirationTime": datetime(2026, 1, 24, 11, 0, 0, tzinfo=UTC),
        "averageMonitoringEnvironmentAltitude": 50.0,
        "wellnessStartTime": datetime(2026, 1, 23, 23, 0, 0, tzinfo=UTC),
        "wellnessEndTime": datetime(2026, 1, 24, 16, 0, 0, tzinfo=UTC),
        "wellnessDistanceMeters": 8000.0,
        "wellnessActiveKilocalories": 500,
        "wellnessKilocalories": 2200,
        "lastSyncTimestamp": datetime(2026, 1, 24, 12, 0, 0, tzinfo=UTC),
    }


def mock_activity_data() -> dict:
    """Sample data for ActivityCoordinator (fetch_activity_data output)."""
    return {
        "lastActivity": {
            "activityId": 12345,
            "activityName": "Morning Run",
            "distance": 5000.0,
            "duration": 1800.0,
            "averageHR": 145,
            "maxHR": 175,
            "calories": 400,
        },
        "lastActivities": [
            {"activityId": 12345, "activityName": "Morning Run"},
            {"activityId": 12344, "activityName": "Walk"},
        ],
        "lastWorkout": {"workoutId": 999, "workoutName": "5k Easy"},
        "workouts": [{"workoutId": 999, "workoutName": "5k Easy"}],
    }


def mock_training_data() -> dict:
    """Sample data for TrainingCoordinator (fetch_training_data output)."""
    return {
        "trainingReadiness": {"score": 72, "level": "GOOD"},
        "trainingStatus": {"trainingStatusPhrase": "PRODUCTIVE"},
        "vo2MaxValue": 37.0,
        "vo2MaxPreciseValue": 37.1,
        "morningTrainingReadiness": {
            "score": 68,
            "level": "FAIR",
            "sleepScore": 82,
            "recoveryScore": 70,
            "hrvStatus": "BALANCED",
        },
        "enduranceScore": {"overallScore": 45, "runningScore": 50},
        "hillScore": {"overallScore": 30, "cyclingScore": 25},
        "lactateThreshold": {
            "speed_and_heart_rate": {"heartRate": 162, "speed": 3.2}
        },
        "hrvStatusText": "Balanced",
        "hrvWeeklyAvg": 45,
        "hrvLastNightAvg": 42,
        "hrvLastNight5MinHigh": 65,
        "hrvBaselineLowUpper": 40,
        "hrvStatus": {
            "status": "BALANCED",
            "weeklyAvg": 45,
            "lastNightAvg": 42,
            "lastNight5MinHigh": 65,
            "baseline": {"lowUpper": 40, "balancedLow": 35, "balancedUpper": 55},
        },
    }


def mock_body_data() -> dict:
    """Sample data for BodyCoordinator (fetch_body_data output)."""
    return {
        "weightKg": 75.0,
        "bmi": 24.5,
        "bodyFat": 18.5,
        "bodyWater": 60.0,
        "boneMassKg": 3.2,
        "muscleMassKg": 35.0,
        "metabolicAge": 32,
        "physiqueRating": 5,
        "visceralFat": 8.0,
        "fitnessAge": 30,
        "chronologicalAge": 35,
        "achievableFitnessAge": 27,
        "previousFitnessAge": 31,
        "valueInML": 1500,
        "goalInML": 2000,
        "dailyAverageInML": 1800,
        "sweatLossInML": 400,
        "activityIntakeInML": 200,
    }


def mock_goals_data() -> dict:
    """Sample data for GoalsCoordinator (fetch_goals_data output)."""
    return {
        "badges": [
            {
                "badgeName": "First 5K",
                "badgePoints": 100,
                "badgeEarnedDate": "2024-01-01T00:00:00",
                "badgeEarnedNumber": 1,
            },
        ],
        "userPoints": 500,
        "userLevel": 5,
        "activeGoals": [
            {
                "name": "Run 100km",
                "type": "distance",
                "distanceInMeters": 100000,
                "startDate": "2026-01-01",
                "endDate": "2026-03-31",
                "activityType": "running",
                "period": "monthly",
                "progress": {"percent": 45},
            }
        ],
        "futureGoals": [],
        "goalsHistory": [],
    }


def mock_gear_data() -> dict:
    """Sample data for GearCoordinator (fetch_gear_data output)."""
    return {
        "gearStats": [
            {
                "uuid": "gear-uuid-1",
                "displayName": "Running Shoes",
                "totalDistance": 500000.0,
                "totalActivities": 50,
                "dateBegin": "2023-01-01",
                "gearMakeName": "Nike",
                "gearModelName": "Pegasus",
                "gearStatusName": "active",
                "maximumMeters": 800000,
                "defaultForActivity": ["running"],
            }
        ],
        "nextAlarm": ["2026-01-25T06:30:00+00:00"],
    }


def mock_blood_pressure_data() -> dict:
    """Sample data for BloodPressureCoordinator."""
    return {
        "bpSystolic": 120,
        "bpDiastolic": 80,
        "bpPulse": 70,
        "bpMeasurementTime": "2026-01-24T08:00:00",
        "bpCategory": 1,
        "bpCategoryName": "Normal",
    }

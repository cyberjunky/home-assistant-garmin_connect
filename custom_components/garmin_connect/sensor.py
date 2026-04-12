"""Sensor platform for Garmin Connect."""

from __future__ import annotations

import datetime
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date as dt_date
from datetime import timedelta
from enum import StrEnum
from typing import Any, cast

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfLength,
    UnitOfMass,
    UnitOfPower,
    UnitOfTime,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import (
    BaseGarminCoordinator,
    GarminConnectConfigEntry,
    GearCoordinator,
    TrainingCoordinator,
)

# Limit parallel updates to prevent API rate limiting
PARALLEL_UPDATES = 1


class CoordinatorType(StrEnum):
    """Enum for coordinator types."""

    CORE = "core"
    ACTIVITY = "activity"
    TRAINING = "training"
    BODY = "body"
    GOALS = "goals"
    GEAR = "gear"
    BLOOD_PRESSURE = "blood_pressure"
    MENSTRUAL = "menstrual"


@dataclass(frozen=True, kw_only=True)
class GarminConnectSensorEntityDescription(SensorEntityDescription):
    """Describes Garmin Connect sensor entity."""

    coordinator_type: CoordinatorType = CoordinatorType.CORE
    """Which coordinator provides data for this sensor."""

    value_fn: Callable[[dict[str, Any]], Any] | None = None
    """Function to extract value from coordinator data (overrides key lookup)."""

    attributes_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None
    """Function to extract extra state attributes from coordinator data."""

    preserve_value: bool = False
    """Retain last known value when API returns None (weight, sleep at midnight, etc)."""


# ── CORE coordinator sensors ─────────────────────────────────────────────────
# Keys match ha_garmin.fetch_core_data() output (incl. _add_computed_fields).

# Activity & Steps Sensors
ACTIVITY_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="totalSteps",
        translation_key="total_steps",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement="steps",
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="dailyStepGoal",
        translation_key="daily_step_goal",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="steps",
    ),
    GarminConnectSensorEntityDescription(
        key="yesterdaySteps",
        translation_key="yesterday_steps",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="steps",
    ),
    GarminConnectSensorEntityDescription(
        key="weeklyStepAvg",
        translation_key="weekly_step_avg",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="steps",
    ),
    GarminConnectSensorEntityDescription(
        key="yesterdayDistance",
        translation_key="yesterday_distance",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfLength.METERS,
        suggested_display_precision=0,
    ),
    GarminConnectSensorEntityDescription(
        key="weeklyDistanceAvg",
        translation_key="weekly_distance_avg",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfLength.METERS,
        suggested_display_precision=0,
    ),
    GarminConnectSensorEntityDescription(
        key="totalDistanceMeters",
        translation_key="total_distance",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfLength.METERS,
        preserve_value=True,
        suggested_display_precision=0,
    ),
    GarminConnectSensorEntityDescription(
        key="floorsAscended",
        translation_key="floors_ascended",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement="floors",
        suggested_display_precision=0,
    ),
    GarminConnectSensorEntityDescription(
        key="floorsDescended",
        translation_key="floors_descended",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement="floors",
        suggested_display_precision=0,
    ),
    GarminConnectSensorEntityDescription(
        key="userFloorsAscendedGoal",
        translation_key="floors_ascended_goal",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="floors",
        suggested_display_precision=0,
    ),
)

# Calories & Nutrition Sensors
CALORIES_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="totalKilocalories",
        translation_key="total_calories",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_CALORIE,
        suggested_display_precision=0,
    ),
    GarminConnectSensorEntityDescription(
        key="activeKilocalories",
        translation_key="active_calories",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_CALORIE,
        suggested_display_precision=0,
    ),
    GarminConnectSensorEntityDescription(
        key="bmrKilocalories",
        translation_key="bmr_calories",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfEnergy.KILO_CALORIE,
        suggested_display_precision=0,
    ),
    GarminConnectSensorEntityDescription(
        key="burnedKilocalories",
        translation_key="burned_calories",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_CALORIE,
        suggested_display_precision=0,
    ),
    GarminConnectSensorEntityDescription(
        key="consumedKilocalories",
        translation_key="consumed_calories",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfEnergy.KILO_CALORIE,
        suggested_display_precision=0,
    ),
    GarminConnectSensorEntityDescription(
        key="remainingKilocalories",
        translation_key="remaining_calories",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfEnergy.KILO_CALORIE,
        suggested_display_precision=0,
    ),
)

# Heart Rate Sensors
HEART_RATE_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="restingHeartRate",
        translation_key="resting_heart_rate",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="bpm",
    ),
    GarminConnectSensorEntityDescription(
        key="maxHeartRate",
        translation_key="max_heart_rate",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="bpm",
    ),
    GarminConnectSensorEntityDescription(
        key="minHeartRate",
        translation_key="min_heart_rate",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="bpm",
    ),
    GarminConnectSensorEntityDescription(
        key="lastSevenDaysAvgRestingHeartRate",
        translation_key="last_7_days_avg_resting_heart_rate",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="bpm",
    ),
)

# Stress Sensors — ha_garmin computes *Minutes from *Duration seconds
STRESS_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="averageStressLevel",
        translation_key="avg_stress_level",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="level",
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="maxStressLevel",
        translation_key="max_stress_level",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="level",
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="stressQualifierText",
        translation_key="stress_qualifier",
    ),
    GarminConnectSensorEntityDescription(
        key="stressMinutes",
        translation_key="total_stress_duration",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
    GarminConnectSensorEntityDescription(
        key="restStressMinutes",
        translation_key="rest_stress_duration",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
    GarminConnectSensorEntityDescription(
        key="activityStressMinutes",
        translation_key="activity_stress_duration",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
    GarminConnectSensorEntityDescription(
        key="lowStressMinutes",
        translation_key="low_stress_duration",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
    GarminConnectSensorEntityDescription(
        key="mediumStressMinutes",
        translation_key="medium_stress_duration",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
    GarminConnectSensorEntityDescription(
        key="highStressMinutes",
        translation_key="high_stress_duration",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
)

# Sleep Sensors — ha_garmin computes *Minutes from *Seconds
SLEEP_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="sleepNeed",
        translation_key="sleep_need",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="bedtime",
        translation_key="bedtime",
        device_class=SensorDeviceClass.TIMESTAMP,
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="optimalBedtime",
        translation_key="optimal_bedtime",
        device_class=SensorDeviceClass.TIMESTAMP,
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="wakeTime",
        translation_key="wake_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="optimalWakeTime",
        translation_key="optimal_wake_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="sleepingMinutes",
        translation_key="sleeping_time",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="sleepTimeMinutes",
        translation_key="total_sleep_duration",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="measurableAsleepDurationMinutes",
        translation_key="sleep_duration",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="measurableAwakeDurationMinutes",
        translation_key="awake_duration",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="sleepScore",
        translation_key="sleep_score",
        state_class=SensorStateClass.MEASUREMENT,
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="deepSleepMinutes",
        translation_key="deep_sleep",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="lightSleepMinutes",
        translation_key="light_sleep",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="remSleepMinutes",
        translation_key="rem_sleep",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="awakeSleepMinutes",
        translation_key="awake_sleep",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="napTimeMinutes",
        translation_key="nap_time",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
    GarminConnectSensorEntityDescription(
        key="unmeasurableSleepMinutes",
        translation_key="unmeasurable_sleep",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
)

# Body Battery Sensors
BODY_BATTERY_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="bodyBatteryMostRecentValue",
        translation_key="body_battery_most_recent",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    GarminConnectSensorEntityDescription(
        key="bodyBatteryHighestValue",
        translation_key="body_battery_highest",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    GarminConnectSensorEntityDescription(
        key="bodyBatteryLowestValue",
        translation_key="body_battery_lowest",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    GarminConnectSensorEntityDescription(
        key="bodyBatteryChargedValue",
        translation_key="body_battery_charged",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=PERCENTAGE,
    ),
    GarminConnectSensorEntityDescription(
        key="bodyBatteryDrainedValue",
        translation_key="body_battery_drained",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=PERCENTAGE,
    ),
)

# Intensity & Activity Time Sensors — ha_garmin computes *Minutes from *Seconds
INTENSITY_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="activeMinutes",
        translation_key="active_time",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="highlyActiveMinutes",
        translation_key="highly_active_time",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
    GarminConnectSensorEntityDescription(
        key="sedentaryMinutes",
        translation_key="sedentary_time",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
    GarminConnectSensorEntityDescription(
        key="moderateIntensityMinutes",
        translation_key="moderate_intensity",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
    GarminConnectSensorEntityDescription(
        key="vigorousIntensityMinutes",
        translation_key="vigorous_intensity",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
    GarminConnectSensorEntityDescription(
        key="intensityMinutesGoal",
        translation_key="intensity_goal",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
    GarminConnectSensorEntityDescription(
        key="totalIntensityMinutes",
        translation_key="total_intensity_minutes",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        attributes_fn=lambda data: {
            "moderate_minutes": data.get("moderateIntensityMinutes"),
            "vigorous_minutes": data.get("vigorousIntensityMinutes"),
            "goal": data.get("intensityMinutesGoal"),
        },
    ),
)

# SPO2 & Respiration Sensors
HEALTH_MONITORING_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="averageSpo2",
        translation_key="avg_spo2",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    GarminConnectSensorEntityDescription(
        key="lowestSpo2",
        translation_key="lowest_spo2",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    GarminConnectSensorEntityDescription(
        key="latestSpo2",
        translation_key="latest_spo2",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    GarminConnectSensorEntityDescription(
        key="latestSpo2ReadingTime",
        translation_key="latest_spo2_time",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    GarminConnectSensorEntityDescription(
        key="highestRespirationValue",
        translation_key="highest_respiration",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="brpm",
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="lowestRespirationValue",
        translation_key="lowest_respiration",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="brpm",
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="latestRespirationValue",
        translation_key="latest_respiration",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="brpm",
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="latestRespirationTime",
        translation_key="latest_respiration_time",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    GarminConnectSensorEntityDescription(
        key="averageMonitoringEnvironmentAltitude",
        translation_key="avg_altitude",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfLength.METERS,
        suggested_display_precision=0,
    ),
)

# Additional Heart Rate Sensors
ADDITIONAL_HEART_RATE_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="minAvgHeartRate",
        translation_key="min_avg_heart_rate",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="bpm",
    ),
    GarminConnectSensorEntityDescription(
        key="maxAvgHeartRate",
        translation_key="max_avg_heart_rate",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="bpm",
    ),
    GarminConnectSensorEntityDescription(
        key="abnormalHeartRateAlertsCount",
        translation_key="abnormal_hr_alerts",
        state_class=SensorStateClass.TOTAL,
    ),
)

# Stress percentage sensors
STRESS_PERCENTAGE_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="stressPercentage",
        translation_key="stress_percentage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    GarminConnectSensorEntityDescription(
        key="restStressPercentage",
        translation_key="rest_stress_percentage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    GarminConnectSensorEntityDescription(
        key="activityStressPercentage",
        translation_key="activity_stress_percentage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    GarminConnectSensorEntityDescription(
        key="uncategorizedStressPercentage",
        translation_key="uncategorized_stress_percentage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    GarminConnectSensorEntityDescription(
        key="lowStressPercentage",
        translation_key="low_stress_percentage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    GarminConnectSensorEntityDescription(
        key="mediumStressPercentage",
        translation_key="medium_stress_percentage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    GarminConnectSensorEntityDescription(
        key="highStressPercentage",
        translation_key="high_stress_percentage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
)

# Additional stress duration sensor
ADDITIONAL_STRESS_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="uncategorizedStressMinutes",
        translation_key="uncategorized_stress_duration",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
)

# Additional distance sensors
ADDITIONAL_DISTANCE_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="floorsAscendedInMeters",
        translation_key="floors_ascended_distance",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfLength.METERS,
        suggested_display_precision=0,
    ),
    GarminConnectSensorEntityDescription(
        key="floorsDescendedInMeters",
        translation_key="floors_descended_distance",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfLength.METERS,
        suggested_display_precision=0,
    ),
)

# Wellness sensors
WELLNESS_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="wellnessStartTime",
        translation_key="wellness_start_time",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    GarminConnectSensorEntityDescription(
        key="wellnessEndTime",
        translation_key="wellness_end_time",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    GarminConnectSensorEntityDescription(
        key="wellnessDistanceMeters",
        translation_key="wellness_distance",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfLength.METERS,
        preserve_value=True,
        suggested_display_precision=0,
    ),
    GarminConnectSensorEntityDescription(
        key="wellnessActiveKilocalories",
        translation_key="wellness_active_calories",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfEnergy.KILO_CALORIE,
        suggested_display_precision=0,
    ),
    GarminConnectSensorEntityDescription(
        key="wellnessKilocalories",
        translation_key="wellness_calories",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfEnergy.KILO_CALORIE,
        suggested_display_precision=0,
    ),
)

# Sync Sensors
SYNC_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="lastSyncTimestamp",
        translation_key="last_synced",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
)

# All CORE sensor descriptions
CORE_SENSOR_DESCRIPTIONS: tuple[GarminConnectSensorEntityDescription, ...] = (
    *ACTIVITY_SENSORS,
    *CALORIES_SENSORS,
    *HEART_RATE_SENSORS,
    *ADDITIONAL_HEART_RATE_SENSORS,
    *STRESS_SENSORS,
    *ADDITIONAL_STRESS_SENSORS,
    *STRESS_PERCENTAGE_SENSORS,
    *SLEEP_SENSORS,
    *BODY_BATTERY_SENSORS,
    *INTENSITY_SENSORS,
    *HEALTH_MONITORING_SENSORS,
    *ADDITIONAL_DISTANCE_SENSORS,
    *WELLNESS_SENSORS,
    *SYNC_SENSORS,
)


# ── ACTIVITY coordinator sensors ──────────────────────────────────────────────
# Data from ha_garmin.fetch_activity_data()

ACTIVITY_TRACKING_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="lastActivity",
        translation_key="last_activity",
        coordinator_type=CoordinatorType.ACTIVITY,
        value_fn=lambda data: (data.get("lastActivity")
                               or {}).get("activityName"),
        attributes_fn=lambda data: data.get("lastActivity") or {},
    ),
    GarminConnectSensorEntityDescription(
        key="lastActivities",
        translation_key="last_activities",
        coordinator_type=CoordinatorType.ACTIVITY,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: len(data.get("lastActivities") or []),
        attributes_fn=lambda data: {
            "last_activities": sorted(
                data.get("lastActivities") or [],
                key=lambda x: x.get("activityId", 0),
            )[-10:]
        },
    ),
    GarminConnectSensorEntityDescription(
        key="lastWorkout",
        translation_key="last_workout",
        coordinator_type=CoordinatorType.ACTIVITY,
        value_fn=lambda data: (data.get("lastWorkout")
                               or {}).get("workoutName"),
        attributes_fn=lambda data: data.get("lastWorkout") or {},
    ),
    GarminConnectSensorEntityDescription(
        key="lastWorkouts",
        translation_key="last_workouts",
        coordinator_type=CoordinatorType.ACTIVITY,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: len(data.get("workouts") or []),
        attributes_fn=lambda data: {
            "last_workouts": (data.get("workouts") or [])[-10:],
        },
    ),
)


# ── TRAINING coordinator sensors ──────────────────────────────────────────────
# Data from ha_garmin.fetch_training_data()

TRAINING_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="enduranceScore",
        translation_key="endurance_score",
        coordinator_type=CoordinatorType.TRAINING,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: (data.get("enduranceScore")
                               or {}).get("overallScore"),
        attributes_fn=lambda data: {
            k: v for k, v in (data.get("enduranceScore") or {}).items() if k != "overallScore"
        },
    ),
    GarminConnectSensorEntityDescription(
        key="hillScore",
        translation_key="hill_score",
        coordinator_type=CoordinatorType.TRAINING,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: (data.get("hillScore")
                               or {}).get("overallScore"),
        attributes_fn=lambda data: {
            k: v for k, v in (data.get("hillScore") or {}).items() if k != "overallScore"
        },
    ),
    GarminConnectSensorEntityDescription(
        key="trainingReadiness",
        translation_key="training_readiness",
        coordinator_type=CoordinatorType.TRAINING,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda data: data.get("trainingReadiness", {}).get("score")
        if isinstance(data.get("trainingReadiness"), dict)
        else (
            data.get("trainingReadiness", [{}])[0].get("score")
            if isinstance(data.get("trainingReadiness"), list) and data.get("trainingReadiness")
            else None
        ),
        attributes_fn=lambda data: data.get("trainingReadiness", {})
        if isinstance(data.get("trainingReadiness"), dict)
        else (
            data.get("trainingReadiness", [{}])[0]
            if isinstance(data.get("trainingReadiness"), list) and data.get("trainingReadiness")
            else {}
        ),
    ),
    GarminConnectSensorEntityDescription(
        key="trainingStatus",
        translation_key="training_status",
        coordinator_type=CoordinatorType.TRAINING,
        value_fn=lambda data: (data.get("trainingStatus")
                               or {}).get("trainingStatusPhrase"),
        attributes_fn=lambda data: data.get("trainingStatus") or {},
    ),
    GarminConnectSensorEntityDescription(
        key="morningTrainingReadiness",
        translation_key="morning_training_readiness",
        coordinator_type=CoordinatorType.TRAINING,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda data: (
            data.get("morningTrainingReadiness") or {}).get("score"),
        attributes_fn=lambda data: {
            "level": (data.get("morningTrainingReadiness") or {}).get("level"),
            "sleep_score": (data.get("morningTrainingReadiness") or {}).get("sleepScore"),
            "recovery_score": (data.get("morningTrainingReadiness") or {}).get("recoveryScore"),
            "hrv_status": (data.get("morningTrainingReadiness") or {}).get("hrvStatus"),
            "acuteLoad": (data.get("morningTrainingReadiness") or {}).get("acuteLoad"),
        },
    ),
    GarminConnectSensorEntityDescription(
        key="lactateThresholdHeartRate",
        translation_key="lactate_threshold_hr",
        coordinator_type=CoordinatorType.TRAINING,
        native_unit_of_measurement="bpm",
        value_fn=lambda data: (
            (data.get("lactateThreshold") or {}).get(
                "speed_and_heart_rate") or {}
        ).get("heartRate"),
        attributes_fn=lambda data: data.get("lactateThreshold") or {},
    ),
    GarminConnectSensorEntityDescription(
        key="lactateThresholdSpeed",
        translation_key="lactate_threshold_speed",
        coordinator_type=CoordinatorType.TRAINING,
        native_unit_of_measurement="m/s",
        value_fn=lambda data: (
            (data.get("lactateThreshold") or {}).get(
                "speed_and_heart_rate") or {}
        ).get("speed"),
        attributes_fn=lambda data: data.get("lactateThreshold") or {},
    ),
    # HRV — ha_garmin flattens hrvStatus from _get_hrv_data_raw via _add_computed_fields
    GarminConnectSensorEntityDescription(
        key="hrvStatusText",
        translation_key="hrv_status",
        coordinator_type=CoordinatorType.TRAINING,
        attributes_fn=lambda data: {
            k: v for k, v in (data.get("hrvStatus") or {}).items() if k != "status"
        },
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="hrvWeeklyAvg",
        translation_key="hrv_weekly_avg",
        coordinator_type=CoordinatorType.TRAINING,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="ms",
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="hrvLastNightAvg",
        translation_key="hrv_last_night_avg",
        coordinator_type=CoordinatorType.TRAINING,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="ms",
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="hrvLastNight5MinHigh",
        translation_key="hrv_last_night_5min_high",
        coordinator_type=CoordinatorType.TRAINING,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="ms",
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="hrvBaselineLowUpper",
        translation_key="hrv_baseline",
        coordinator_type=CoordinatorType.TRAINING,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="ms",
        attributes_fn=lambda data: (
            data.get("hrvStatus") or {}).get("baseline") or {},
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="vo2Max",
        translation_key="vo2_max",
        coordinator_type=CoordinatorType.TRAINING,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="mL/(kg·min)",
        value_fn=lambda data: data.get("vo2MaxValue") or (
            ((data.get("trainingStatus") or {}).get("mostRecentVO2Max") or {})
            .get("generic", {})
            .get("vo2MaxValue")
        ),
    ),
)


# ── BODY coordinator sensors ──────────────────────────────────────────────────
# Data from ha_garmin.fetch_body_data()
# ha_garmin computes weightKg, boneMassKg, muscleMassKg via _add_computed_fields

BODY_COMPOSITION_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="weightKg",
        translation_key="weight",
        coordinator_type=CoordinatorType.BODY,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="bmi",
        translation_key="bmi",
        coordinator_type=CoordinatorType.BODY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="BMI",
        preserve_value=True,
        suggested_display_precision=1,
    ),
    GarminConnectSensorEntityDescription(
        key="bodyFat",
        translation_key="body_fat",
        coordinator_type=CoordinatorType.BODY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="bodyWater",
        translation_key="body_water",
        coordinator_type=CoordinatorType.BODY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="boneMassKg",
        translation_key="bone_mass",
        coordinator_type=CoordinatorType.BODY,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="muscleMassKg",
        translation_key="muscle_mass",
        coordinator_type=CoordinatorType.BODY,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        preserve_value=True,
    ),
)

HYDRATION_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="valueInML",
        translation_key="hydration",
        coordinator_type=CoordinatorType.BODY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolume.MILLILITERS,
        suggested_display_precision=0,
    ),
    GarminConnectSensorEntityDescription(
        key="goalInML",
        translation_key="hydration_goal",
        coordinator_type=CoordinatorType.BODY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolume.MILLILITERS,
        suggested_display_precision=0,
    ),
    GarminConnectSensorEntityDescription(
        key="dailyAverageInML",
        translation_key="hydration_daily_average",
        coordinator_type=CoordinatorType.BODY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolume.MILLILITERS,
        suggested_display_precision=0,
    ),
    GarminConnectSensorEntityDescription(
        key="sweatLossInML",
        translation_key="hydration_sweat_loss",
        coordinator_type=CoordinatorType.BODY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolume.MILLILITERS,
        suggested_display_precision=0,
    ),
    GarminConnectSensorEntityDescription(
        key="activityIntakeInML",
        translation_key="hydration_activity_intake",
        coordinator_type=CoordinatorType.BODY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolume.MILLILITERS,
        suggested_display_precision=0,
    ),
)

FITNESS_AGE_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="chronologicalAge",
        translation_key="chronological_age",
        coordinator_type=CoordinatorType.BODY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.YEARS,
        suggested_display_precision=0,
    ),
    GarminConnectSensorEntityDescription(
        key="fitnessAge",
        translation_key="fitness_age",
        coordinator_type=CoordinatorType.BODY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.YEARS,
        suggested_display_precision=1,
    ),
    GarminConnectSensorEntityDescription(
        key="achievableFitnessAge",
        translation_key="achievable_fitness_age",
        coordinator_type=CoordinatorType.BODY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.YEARS,
        suggested_display_precision=1,
    ),
    GarminConnectSensorEntityDescription(
        key="previousFitnessAge",
        translation_key="previous_fitness_age",
        coordinator_type=CoordinatorType.BODY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.YEARS,
        suggested_display_precision=1,
    ),
    GarminConnectSensorEntityDescription(
        key="metabolicAge",
        translation_key="metabolic_age",
        coordinator_type=CoordinatorType.BODY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.YEARS,
        preserve_value=True,
        suggested_display_precision=0,
    ),
    GarminConnectSensorEntityDescription(
        key="physiqueRating",
        translation_key="physique_rating",
        coordinator_type=CoordinatorType.BODY,
        state_class=SensorStateClass.MEASUREMENT,
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="visceralFat",
        translation_key="visceral_fat",
        coordinator_type=CoordinatorType.BODY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        preserve_value=True,
    ),
)


# ── GOALS coordinator sensors ─────────────────────────────────────────────────
# Data from ha_garmin.fetch_goals_data()

GOALS_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="badges",
        translation_key="badges",
        coordinator_type=CoordinatorType.GOALS,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: len(data.get("badges", [])),
        attributes_fn=lambda data: {
            "badges": [
                {
                    "name": b.get("badgeName"),
                    "points": b.get("badgePoints"),
                    "earned_date": b.get("badgeEarnedDate", "")[:10]
                    if b.get("badgeEarnedDate")
                    else None,
                    "times_earned": b.get("badgeEarnedNumber"),
                }
                for b in sorted(
                    data.get("badges", []),
                    key=lambda x: x.get("badgeEarnedDate", ""),
                    reverse=True,
                )[:10]
            ],
        },
    ),
    GarminConnectSensorEntityDescription(
        key="userPoints",
        translation_key="user_points",
        coordinator_type=CoordinatorType.GOALS,
        state_class=SensorStateClass.TOTAL,
    ),
    GarminConnectSensorEntityDescription(
        key="userLevel",
        translation_key="user_level",
        coordinator_type=CoordinatorType.GOALS,
        state_class=SensorStateClass.TOTAL,
    ),
    GarminConnectSensorEntityDescription(
        key="activeGoals",
        translation_key="active_goals",
        coordinator_type=CoordinatorType.GOALS,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: len(data.get("activeGoals", [])),
        attributes_fn=lambda data: {
            "goals": [
                {
                    "name": g.get("name"),
                    "type": g.get("type"),
                    "target_distance": g.get("distanceInMeters"),
                    "target_duration": g.get("durationInSeconds"),
                    "target_calories": g.get("caloriesInKiloCalories"),
                    "target_activities": g.get("numberOfActivities"),
                    "progress_percent": g.get("progress", {}).get("percent"),
                    "start_date": g.get("startDate"),
                    "end_date": g.get("endDate"),
                    "activity_type": g.get("activityType"),
                    "period": g.get("period"),
                }
                for g in data.get("activeGoals", [])
            ],
        },
    ),
    GarminConnectSensorEntityDescription(
        key="futureGoals",
        translation_key="future_goals",
        coordinator_type=CoordinatorType.GOALS,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: len(data.get("futureGoals", [])),
        attributes_fn=lambda data: {
            "goals": [
                {
                    "name": g.get("name"),
                    "type": g.get("type"),
                    "target_distance": g.get("distanceInMeters"),
                    "target_duration": g.get("durationInSeconds"),
                    "start_date": g.get("startDate"),
                    "end_date": g.get("endDate"),
                    "activity_type": g.get("activityType"),
                }
                for g in data.get("futureGoals", [])
            ],
        },
    ),
    GarminConnectSensorEntityDescription(
        key="goalsHistory",
        translation_key="goals_history",
        coordinator_type=CoordinatorType.GOALS,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: len(data.get("goalsHistory", [])),
        attributes_fn=lambda data: {
            "goals": [
                {
                    "name": g.get("name"),
                    "type": g.get("type"),
                    "progress_percent": g.get("progress", {}).get("percent"),
                    "start_date": g.get("startDate"),
                    "end_date": g.get("endDate"),
                }
                for g in data.get("goalsHistory", [])
            ],
        },
    ),
)


def _parse_iso(value: str) -> datetime.datetime | None:
    """Parse an ISO datetime string, returning None on failure."""
    try:
        return datetime.datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


# ── GEAR coordinator sensors ──────────────────────────────────────────────────
# Data from ha_garmin.fetch_gear_data() — dynamic gear sensors

GEAR_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="nextAlarm",
        translation_key="next_alarm",
        coordinator_type=CoordinatorType.GEAR,
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: next(
            (
                dt
                for a in (data.get("nextAlarm") or [])
                if isinstance(a, str)
                for dt in [_parse_iso(a)]
                if dt is not None
            ),
            None,
        ),
        attributes_fn=lambda data: {"next_alarms": data.get("nextAlarm")},
    ),
)


# ── BLOOD PRESSURE coordinator sensors ────────────────────────────────────────
# Data from ha_garmin.fetch_blood_pressure_data()

BLOOD_PRESSURE_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="bpSystolic",
        translation_key="bp_systolic",
        coordinator_type=CoordinatorType.BLOOD_PRESSURE,
        native_unit_of_measurement="mmHg",
        state_class=SensorStateClass.MEASUREMENT,
        preserve_value=True,
        attributes_fn=lambda data: {
            k: v
            for k, v in {
                "diastolic": data.get("bpDiastolic"),
                "pulse": data.get("bpPulse"),
                "measurement_time": data.get("bpMeasurementTime"),
                "category": data.get("bpCategory"),
                "category_name": data.get("bpCategoryName"),
            }.items()
            if v is not None
        },
    ),
    GarminConnectSensorEntityDescription(
        key="bpDiastolic",
        translation_key="bp_diastolic",
        coordinator_type=CoordinatorType.BLOOD_PRESSURE,
        native_unit_of_measurement="mmHg",
        state_class=SensorStateClass.MEASUREMENT,
        preserve_value=True,
        attributes_fn=lambda data: {
            k: v
            for k, v in {
                "systolic": data.get("bpSystolic"),
                "pulse": data.get("bpPulse"),
                "measurement_time": data.get("bpMeasurementTime"),
                "category": data.get("bpCategory"),
                "category_name": data.get("bpCategoryName"),
            }.items()
            if v is not None
        },
    ),
    GarminConnectSensorEntityDescription(
        key="bpPulse",
        translation_key="bp_pulse",
        coordinator_type=CoordinatorType.BLOOD_PRESSURE,
        native_unit_of_measurement="bpm",
        state_class=SensorStateClass.MEASUREMENT,
        preserve_value=True,
        attributes_fn=lambda data: {
            k: v
            for k, v in {
                "systolic": data.get("bpSystolic"),
                "diastolic": data.get("bpDiastolic"),
                "measurement_time": data.get("bpMeasurementTime"),
                "category": data.get("bpCategory"),
                "category_name": data.get("bpCategoryName"),
            }.items()
            if v is not None
        },
    ),
    GarminConnectSensorEntityDescription(
        key="bpCategoryName",
        translation_key="bp_category",
        coordinator_type=CoordinatorType.BLOOD_PRESSURE,
        preserve_value=True,
        attributes_fn=lambda data: {
            k: v
            for k, v in {
                "systolic": data.get("bpSystolic"),
                "diastolic": data.get("bpDiastolic"),
                "category_code": data.get("bpCategory"),
                "measurement_time": data.get("bpMeasurementTime"),
            }.items()
            if v is not None
        },
    ),
    GarminConnectSensorEntityDescription(
        key="bpMeasurementTime",
        translation_key="bp_measurement_time",
        coordinator_type=CoordinatorType.BLOOD_PRESSURE,
        preserve_value=True,
    ),
)


# ── MENSTRUAL coordinator sensors ─────────────────────────────────────────────
# Data from ha_garmin.fetch_menstrual_data() — all disabled by default

_MENSTRUAL_PHASE_MAP = {
    1: "Menstruation",
    2: "Follicular",
    3: "Ovulation",
    4: "Luteal",
}


def _menstrual_day_summary(data: dict[str, Any]) -> dict[str, Any]:
    """Safely return menstrual daySummary dict."""
    return (data.get("menstrualData") or {}).get("daySummary") or {}


def _menstrual_calendar_summaries(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Safely return menstrual calendar cycleSummaries list."""
    return (data.get("menstrualCalendar") or {}).get("cycleSummaries") or []


def _menstrual_next_predicted_cycle_start(data: dict[str, Any]) -> str | None:
    """Return next predicted cycle startDate from calendar."""
    today = dt_date.today()
    for cycle in _menstrual_calendar_summaries(data):
        if cycle.get("predictedCycle") is True:
            start = cycle.get("startDate")
            if not isinstance(start, str):
                continue
            try:
                d = datetime.datetime.strptime(start, "%Y-%m-%d").date()
            except ValueError:
                continue
            if d >= today:
                return str(start)
    return None


def _menstrual_fertile_window_start(data: dict[str, Any]) -> str | None:
    """Compute fertile window start date from cycle start + offset."""
    s = _menstrual_day_summary(data)
    start = s.get("startDate")
    fw_start = s.get("fertileWindowStart")
    if not start or not isinstance(fw_start, int):
        return None
    try:
        start_date = datetime.datetime.strptime(start, "%Y-%m-%d").date()
    except ValueError:
        return None
    return (start_date + timedelta(days=fw_start - 1)).isoformat()


def _menstrual_fertile_window_end(data: dict[str, Any]) -> str | None:
    """Compute fertile window end date from start + length."""
    s = _menstrual_day_summary(data)
    start = s.get("startDate")
    fw_start = s.get("fertileWindowStart")
    fw_len = s.get("lengthOfFertileWindow")
    if not start or not isinstance(fw_start, int) or not isinstance(fw_len, int) or fw_len <= 0:
        return None
    try:
        start_date = datetime.datetime.strptime(start, "%Y-%m-%d").date()
    except ValueError:
        return None
    fertile_start = start_date + timedelta(days=fw_start - 1)
    return (fertile_start + timedelta(days=fw_len - 1)).isoformat()


MENSTRUAL_CYCLE_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="menstrualCyclePhase",
        translation_key="menstrual_cycle_phase",
        coordinator_type=CoordinatorType.MENSTRUAL,
        entity_registry_enabled_default=False,
        value_fn=lambda data: (
            _MENSTRUAL_PHASE_MAP.get(
                int(_menstrual_day_summary(data)["currentPhase"]), "Unknown")
            if isinstance(_menstrual_day_summary(data).get("currentPhase"), int)
            else None
        ),
        attributes_fn=lambda data: {
            "cycle_start_date": _menstrual_day_summary(data).get("startDate"),
            "day_in_cycle": _menstrual_day_summary(data).get("dayInCycle"),
            "period_length": _menstrual_day_summary(data).get("periodLength"),
            "cycle_type": _menstrual_day_summary(data).get("cycleType"),
            "days_until_next_phase": _menstrual_day_summary(data).get("daysUntilNextPhase"),
        },
    ),
    GarminConnectSensorEntityDescription(
        key="menstrualCycleDay",
        translation_key="menstrual_cycle_day",
        coordinator_type=CoordinatorType.MENSTRUAL,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _menstrual_day_summary(data).get("dayInCycle"),
    ),
    GarminConnectSensorEntityDescription(
        key="menstrualDaysUntilNextPhase",
        translation_key="menstrual_days_until_next_phase",
        coordinator_type=CoordinatorType.MENSTRUAL,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _menstrual_day_summary(
            data).get("daysUntilNextPhase"),
    ),
    GarminConnectSensorEntityDescription(
        key="menstrualCycleStart",
        translation_key="menstrual_cycle_start",
        coordinator_type=CoordinatorType.MENSTRUAL,
        device_class=SensorDeviceClass.DATE,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _menstrual_day_summary(data).get("startDate"),
    ),
    GarminConnectSensorEntityDescription(
        key="menstrualNextPredictedCycleStart",
        translation_key="menstrual_next_predicted_cycle_start",
        coordinator_type=CoordinatorType.MENSTRUAL,
        device_class=SensorDeviceClass.DATE,
        entity_registry_enabled_default=False,
        value_fn=_menstrual_next_predicted_cycle_start,
    ),
    GarminConnectSensorEntityDescription(
        key="menstrualFertileWindowStart",
        translation_key="menstrual_fertile_window_start",
        coordinator_type=CoordinatorType.MENSTRUAL,
        device_class=SensorDeviceClass.DATE,
        entity_registry_enabled_default=False,
        value_fn=_menstrual_fertile_window_start,
    ),
    GarminConnectSensorEntityDescription(
        key="menstrualFertileWindowEnd",
        translation_key="menstrual_fertile_window_end",
        coordinator_type=CoordinatorType.MENSTRUAL,
        device_class=SensorDeviceClass.DATE,
        entity_registry_enabled_default=False,
        value_fn=_menstrual_fertile_window_end,
    ),
    GarminConnectSensorEntityDescription(
        key="menstrualPeriodLength",
        translation_key="menstrual_period_length",
        coordinator_type=CoordinatorType.MENSTRUAL,
        native_unit_of_measurement=UnitOfTime.DAYS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _menstrual_day_summary(data).get("periodLength"),
    ),
    GarminConnectSensorEntityDescription(
        key="menstrualCycleType",
        translation_key="menstrual_cycle_type",
        coordinator_type=CoordinatorType.MENSTRUAL,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _menstrual_day_summary(data).get("cycleType"),
    ),
)


# ── Map coordinator type → (descriptions, coordinator instance attr) ──────────

_COORDINATOR_SENSOR_MAP: tuple[
    tuple[CoordinatorType, tuple[GarminConnectSensorEntityDescription, ...]], ...
] = (
    (CoordinatorType.CORE, CORE_SENSOR_DESCRIPTIONS),
    (CoordinatorType.ACTIVITY, ACTIVITY_TRACKING_SENSORS),
    (CoordinatorType.TRAINING, TRAINING_SENSORS),
    (CoordinatorType.BODY, (*BODY_COMPOSITION_SENSORS,
     *HYDRATION_SENSORS, *FITNESS_AGE_SENSORS)),
    (CoordinatorType.GOALS, GOALS_SENSORS),
    (CoordinatorType.GEAR, GEAR_SENSORS),
    (CoordinatorType.BLOOD_PRESSURE, BLOOD_PRESSURE_SENSORS),
    (CoordinatorType.MENSTRUAL, MENSTRUAL_CYCLE_SENSORS),
)

_COORDINATOR_ATTR: dict[CoordinatorType, str] = {
    CoordinatorType.CORE: "core",
    CoordinatorType.ACTIVITY: "activity",
    CoordinatorType.TRAINING: "training",
    CoordinatorType.BODY: "body",
    CoordinatorType.GOALS: "goals",
    CoordinatorType.GEAR: "gear",
    CoordinatorType.BLOOD_PRESSURE: "blood_pressure",
    CoordinatorType.MENSTRUAL: "menstrual",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GarminConnectConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Garmin Connect sensors."""
    coordinators = entry.runtime_data

    entities: list[GarminConnectSensor | GarminConnectGearSensor |
                   GarminConnectPowerToWeightSensor] = []

    for coord_type, descriptions in _COORDINATOR_SENSOR_MAP:
        coordinator = getattr(coordinators, _COORDINATOR_ATTR[coord_type])
        for description in descriptions:
            entities.append(GarminConnectSensor(
                coordinator, description, entry.entry_id))

    # Migrate the legacy entity_id created from duplicate translated names:
    # sleepTimeMinutes was previously shown as "Sleep duration", which often
    # resulted in entity_id suffixes like sensor.garmin_connect_sleep_duration_2.
    ent_reg = er.async_get(hass)

    # Find and rename the _2 suffixed sleep duration entity if it exists
    for entity in ent_reg.entities.values():
        if (
            entity.domain == "sensor"
            and entity.platform == DOMAIN
            and entity.entity_id == "sensor.garmin_connect_sleep_duration_2"
        ):
            try:
                ent_reg.async_update_entity(
                    entity.entity_id,
                    new_entity_id="sensor.garmin_connect_sleep_duration",
                )
            except (ValueError, KeyError):
                pass
            break

    # Migrate gear sensor unique_ids from old name-slug format to UUID format.
    # Previously: f"{entry_id}_gear_{name.lower().replace(' ', '_').replace('-', '_')}"
    # Now:        f"{entry_id}_gear_{gear_uuid}"

    gear_data = coordinators.gear.data or {}
    for gear_stat in gear_data.get("gearStats", []):
        gear_name = gear_stat.get("displayName") or gear_stat.get(
            "gearName") or "Unknown"
        gear_uuid = gear_stat.get("uuid") or gear_stat.get("gearUuid", "")
        if not gear_uuid:
            continue
        old_unique_id = (
            f"{entry.entry_id}_gear_"
            f"{gear_name.lower().replace(' ', '_').replace('-', '_')}"
        )
        new_unique_id = f"{entry.entry_id}_gear_{gear_uuid}"
        if old_unique_id != new_unique_id:
            entity_id = ent_reg.async_get_entity_id(
                "sensor", DOMAIN, old_unique_id)
            if entity_id:
                ent_reg.async_update_entity(
                    entity_id, new_unique_id=new_unique_id)

    # Dynamic gear sensors
    for gear_stat in gear_data.get("gearStats", []):
        gear_name = gear_stat.get("displayName") or gear_stat.get(
            "gearName") or "Unknown"
        gear_uuid = gear_stat.get("uuid") or gear_stat.get("gearUuid", "")
        if gear_uuid:
            entities.append(
                GarminConnectGearSensor(
                    coordinators.gear,
                    gear_uuid=gear_uuid,
                    gear_name=gear_name,
                    entry_id=entry.entry_id,
                )
            )

    # Dynamic power-to-weight sensors (one PTW + one FTP sensor per sport)
    ptw_list: list[dict[str, Any]] = (
        coordinators.training.data or {}).get("powerToWeight") or []
    for ptw_entry in ptw_list:
        sport = ptw_entry.get("sport")
        if not sport:
            continue
        for sensor_type in ("ptw", "ftp"):
            entities.append(
                GarminConnectPowerToWeightSensor(
                    coordinators.training,
                    sport=sport,
                    sensor_type=sensor_type,
                    entry_id=entry.entry_id,
                )
            )

    async_add_entities(entities)


class GarminConnectSensor(CoordinatorEntity[BaseGarminCoordinator], SensorEntity):
    """Representation of a Garmin Connect sensor."""

    entity_description: GarminConnectSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BaseGarminCoordinator,
        description: GarminConnectSensorEntityDescription,
        entry_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Garmin Connect",
            manufacturer="Garmin",
            entry_type=DeviceEntryType.SERVICE,
        )
        self._last_known_value: str | int | float | datetime.datetime | None = None

    @property
    def native_value(self) -> str | int | float | datetime.datetime | None:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return (
                self._last_known_value
                if self.entity_description.preserve_value
                else None
            )

        if self.entity_description.value_fn is not None:
            raw = self.entity_description.value_fn(self.coordinator.data)
        else:
            raw = self.coordinator.data.get(self.entity_description.key)

        # Explicitly narrow the type for mypy
        value = cast(str | int | float | datetime.datetime | None, raw)

        if value is None:
            return (
                self._last_known_value
                if self.entity_description.preserve_value
                else None
            )

        if self.entity_description.preserve_value:
            self._last_known_value = value

        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        if not self.coordinator.data or self.entity_description.attributes_fn is None:
            return {}
        return self.entity_description.attributes_fn(self.coordinator.data)


class GarminConnectGearSensor(CoordinatorEntity[GearCoordinator], SensorEntity):
    """Representation of a dynamic Garmin Connect gear sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GearCoordinator,
        gear_uuid: str,
        gear_name: str,
        entry_id: str,
    ) -> None:
        """Initialize the gear sensor."""
        super().__init__(coordinator)
        self._gear_uuid = gear_uuid
        self._gear_name = gear_name or "Unknown"
        self._attr_native_unit_of_measurement = UnitOfLength.METERS
        self._attr_device_class = SensorDeviceClass.DISTANCE
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_suggested_display_precision = 0
        self._attr_unique_id = f"{entry_id}_gear_{gear_uuid}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Garmin Connect",
            manufacturer="Garmin",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._gear_name

    @property
    def native_value(self) -> float | int | None:
        """Return total distance for this gear in meters."""
        if not self.coordinator.data:
            return None

        gear_stats = self.coordinator.data.get("gearStats", [])
        for gear_stat in gear_stats:
            if (gear_stat.get("uuid") or gear_stat.get("gearUuid")) == self._gear_uuid:
                raw = gear_stat.get("totalDistance")
                return cast(float | int | None, raw)

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return gear details as attributes."""
        if not self.coordinator.data:
            return {}
        for gear_stat in self.coordinator.data.get("gearStats", []):
            if (gear_stat.get("uuid") or gear_stat.get("gearUuid")) == self._gear_uuid:
                return {
                    "gear_uuid": self._gear_uuid,
                    "total_activities": gear_stat.get("totalActivities"),
                    "date_begin": gear_stat.get("dateBegin"),
                    "date_end": gear_stat.get("dateEnd"),
                    "gear_make_name": gear_stat.get("gearMakeName"),
                    "gear_model_name": gear_stat.get("gearModelName"),
                    "gear_status_name": gear_stat.get("gearStatusName"),
                    "custom_make_model": gear_stat.get("customMakeModel"),
                    "maximum_meters": gear_stat.get("maximumMeters"),
                    "default_for_activity": gear_stat.get("defaultForActivity", []),
                }
        return {}


class GarminConnectPowerToWeightSensor(CoordinatorEntity[TrainingCoordinator], SensorEntity):
    """Representation of a dynamic Garmin Connect power-to-weight or FTP sensor."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: TrainingCoordinator,
        sport: str,
        sensor_type: str,
        entry_id: str,
    ) -> None:
        """Initialize the power-to-weight sensor.

        sensor_type must be 'ptw' (power-to-weight in W/kg) or 'ftp' (watts).
        """
        super().__init__(coordinator)
        self._sport = sport
        self._sensor_type = sensor_type
        sport_display = sport.replace("_", " ").title()
        if sensor_type == "ptw":
            self._attr_name = f"Power to Weight {sport_display}"
            self._attr_native_unit_of_measurement = "W/kg"
            self._attr_suggested_display_precision = 2
        else:
            self._attr_name = f"FTP {sport_display}"
            self._attr_native_unit_of_measurement = UnitOfPower.WATT
            self._attr_device_class = SensorDeviceClass.POWER
        self._attr_unique_id = f"{entry_id}_{sensor_type}_{sport.lower()}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Garmin Connect",
            manufacturer="Garmin",
            entry_type=DeviceEntryType.SERVICE,
        )

    def _get_entry(self) -> dict[str, Any] | None:
        """Return the powerToWeight entry for this sport, or None."""
        ptw_list: list[dict[str, Any]] = (
            self.coordinator.data or {}
        ).get("powerToWeight") or []
        for entry in ptw_list:
            if entry.get("sport") == self._sport:
                return entry
        return None

    @property
    def native_value(self) -> float | int | None:
        """Return the sensor value."""
        entry = self._get_entry()
        if entry is None:
            return None
        key = "powerToWeight" if self._sensor_type == "ptw" else "functionalThresholdPower"
        return cast(float | int | None, entry.get(key))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        entry = self._get_entry()
        if entry is None:
            return {}
        attrs: dict[str, Any] = {
            "sport": self._sport,
            "weight_kg": entry.get("weight"),
            "calendar_date": entry.get("calendarDate"),
            "ftp_created": entry.get("ftpCreateTime"),
            "weight_created": entry.get("weightCreateTime"),
            "is_stale": entry.get("isStale"),
        }
        if self._sensor_type == "ptw":
            attrs["ftp"] = entry.get("functionalThresholdPower")
        else:
            attrs["power_to_weight"] = entry.get("powerToWeight")
        return attrs

"""Sensor entity descriptions for Garmin Connect integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfLength,
    UnitOfMass,
    UnitOfTime,
    UnitOfVolume,
)

# Essential keys to keep when trimming activity data for attributes
# This reduces ~3KB per activity to ~500 bytes to stay under HA's 16KB limit
ACTIVITY_ESSENTIAL_KEYS = {
    # Identity
    "activityId",
    "activityName",
    # Time
    "startTimeLocal",
    "startTimeGMT",
    "duration",
    "movingDuration",
    "elapsedDuration",
    # Distance/Speed
    "distance",
    "averageSpeed",
    "maxSpeed",
    # Location
    "locationName",
    "startLatitude",
    "startLongitude",
    "endLatitude",
    "endLongitude",
    # Heart Rate
    "averageHR",
    "maxHR",
    # Stats
    "calories",
    "steps",
    "elevationGain",
    "elevationLoss",
    # Cadence
    "averageRunningCadenceInStepsPerMinute",
    "maxRunningCadenceInStepsPerMinute",
    # Type (simplified)
    "activityType",
}


def _trim_activity(activity: dict) -> dict:
    """Trim activity to essential fields only to reduce attribute size."""
    trimmed = {k: v for k, v in activity.items() if k in ACTIVITY_ESSENTIAL_KEYS}
    # Simplify activityType to just typeKey
    if "activityType" in trimmed and isinstance(trimmed["activityType"], dict):
        trimmed["activityType"] = trimmed["activityType"].get("typeKey", "unknown")
    return trimmed


@dataclass(frozen=True, kw_only=True)
class GarminConnectSensorEntityDescription(SensorEntityDescription):
    """Describes Garmin Connect sensor entity."""

    value_fn: Callable[[dict[str, Any]], Any] | None = None
    """Function to extract value from coordinator data."""

    attributes_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None
    """Function to extract attributes from coordinator data."""

    preserve_value: bool = False
    """If True, preserve last known value when API returns None (for weight, BMI, etc)."""



# Activity & Steps Sensors
ACTIVITY_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="totalSteps",
        translation_key="total_steps",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="steps",
        icon="mdi:walk",
    ),
    GarminConnectSensorEntityDescription(
        key="dailyStepGoal",
        translation_key="daily_step_goal",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="steps",
        icon="mdi:target",
    ),
    GarminConnectSensorEntityDescription(
        key="yesterdaySteps",
        translation_key="yesterday_steps",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="steps",
        icon="mdi:walk",
    ),
    GarminConnectSensorEntityDescription(
        key="weeklyStepAvg",
        translation_key="weekly_step_avg",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="steps",
        icon="mdi:chart-line",
    ),
    GarminConnectSensorEntityDescription(
        key="yesterdayDistance",
        translation_key="yesterday_distance",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfLength.METERS,
        icon="mdi:map-marker-distance",
    ),
    GarminConnectSensorEntityDescription(
        key="weeklyDistanceAvg",
        translation_key="weekly_distance_avg",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfLength.METERS,
        icon="mdi:chart-line",
    ),
    GarminConnectSensorEntityDescription(
        key="totalDistanceMeters",
        translation_key="total_distance",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfLength.METERS,
        icon="mdi:walk",
    ),
    GarminConnectSensorEntityDescription(
        key="floorsAscended",
        translation_key="floors_ascended",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="floors",
        icon="mdi:stairs-up",
    ),
    GarminConnectSensorEntityDescription(
        key="floorsDescended",
        translation_key="floors_descended",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="floors",
        icon="mdi:stairs-down",
    ),
    GarminConnectSensorEntityDescription(
        key="userFloorsAscendedGoal",
        translation_key="floors_ascended_goal",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="floors",
        icon="mdi:target",
    ),
)

# Calories & Nutrition Sensors
CALORIES_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="totalKilocalories",
        translation_key="total_calories",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kcal",
        icon="mdi:fire",
    ),
    GarminConnectSensorEntityDescription(
        key="activeKilocalories",
        translation_key="active_calories",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kcal",
        icon="mdi:fire",
    ),
    GarminConnectSensorEntityDescription(
        key="bmrKilocalories",
        translation_key="bmr_calories",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kcal",
        icon="mdi:fire-circle",
    ),
    GarminConnectSensorEntityDescription(
        key="burnedKilocalories",
        translation_key="burned_calories",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kcal",
        icon="mdi:fire",
    ),
    GarminConnectSensorEntityDescription(
        key="consumedKilocalories",
        translation_key="consumed_calories",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kcal",
        icon="mdi:food",

    ),
    GarminConnectSensorEntityDescription(
        key="remainingKilocalories",
        translation_key="remaining_calories",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kcal",
        icon="mdi:food",

    ),
)

# Heart Rate Sensors
HEART_RATE_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="restingHeartRate",
        translation_key="resting_heart_rate",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="bpm",
        icon="mdi:heart-pulse",
    ),
    GarminConnectSensorEntityDescription(
        key="maxHeartRate",
        translation_key="max_heart_rate",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="bpm",
        icon="mdi:heart-pulse",
    ),
    GarminConnectSensorEntityDescription(
        key="minHeartRate",
        translation_key="min_heart_rate",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="bpm",
        icon="mdi:heart-pulse",
    ),
    GarminConnectSensorEntityDescription(
        key="lastSevenDaysAvgRestingHeartRate",
        translation_key="last_7_days_avg_resting_heart_rate",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="bpm",
        icon="mdi:heart-pulse",

    ),
    GarminConnectSensorEntityDescription(
        key="hrvStatus",
        translation_key="hrv_status",
        icon="mdi:heart-pulse",
        value_fn=lambda data: data.get("hrvStatus", {}).get(
            "status", "").capitalize() if data.get("hrvStatus") else None,
        attributes_fn=lambda data: {k: v for k, v in data.get(
            "hrvStatus", {}).items() if k != "status"} if data.get("hrvStatus") else {},
    ),
    GarminConnectSensorEntityDescription(
        key="hrvWeeklyAvg",
        translation_key="hrv_weekly_avg",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="ms",
        icon="mdi:heart-pulse",
        value_fn=lambda data: data.get("hrvStatus", {}).get("weeklyAvg"),
    ),
    GarminConnectSensorEntityDescription(
        key="hrvLastNightAvg",
        translation_key="hrv_last_night_avg",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="ms",
        icon="mdi:heart-pulse",
        value_fn=lambda data: data.get("hrvStatus", {}).get("lastNightAvg"),
    ),
    GarminConnectSensorEntityDescription(
        key="hrvLastNight5MinHigh",
        translation_key="hrv_last_night_5min_high",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="ms",
        icon="mdi:heart-pulse",
        value_fn=lambda data: data.get("hrvStatus", {}).get("lastNight5MinHigh"),
    ),
    GarminConnectSensorEntityDescription(
        key="hrvBaseline",
        translation_key="hrv_baseline",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="ms",
        icon="mdi:heart-pulse",
        value_fn=lambda data: data.get("hrvStatus", {}).get("baseline", {}).get(
            "lowUpper") if data.get("hrvStatus", {}).get("baseline") else None,
        attributes_fn=lambda data: data.get("hrvStatus", {}).get("baseline", {}),
    ),
)

# Stress Sensors
STRESS_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="averageStressLevel",
        translation_key="avg_stress_level",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="level",
        icon="mdi:gauge",
    ),
    GarminConnectSensorEntityDescription(
        key="maxStressLevel",
        translation_key="max_stress_level",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="level",
        icon="mdi:gauge-full",
    ),
    GarminConnectSensorEntityDescription(
        key="stressQualifier",
        translation_key="stress_qualifier",
        icon="mdi:emoticon",
        value_fn=lambda data: data.get("stressQualifier", "").capitalize(
        ) if data.get("stressQualifier") else None,

    ),
    GarminConnectSensorEntityDescription(
        key="totalStressDuration",
        translation_key="total_stress_duration",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:timer",
        value_fn=lambda data: round(data.get(
            "totalStressDuration", 0) / 60, 2) if data.get("totalStressDuration") else None,
    ),
    GarminConnectSensorEntityDescription(
        key="restStressDuration",
        translation_key="rest_stress_duration",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:timer-pause",
        value_fn=lambda data: round(data.get(
            "restStressDuration", 0) / 60, 2) if data.get("restStressDuration") else None,
    ),
    GarminConnectSensorEntityDescription(
        key="activityStressDuration",
        translation_key="activity_stress_duration",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:timer-play",
        value_fn=lambda data: round(data.get(
            "activityStressDuration", 0) / 60, 2) if data.get("activityStressDuration") else None,
    ),
    GarminConnectSensorEntityDescription(
        key="lowStressDuration",
        translation_key="low_stress_duration",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:timer-check",
        value_fn=lambda data: round(data.get(
            "lowStressDuration", 0) / 60, 2) if data.get("lowStressDuration") else None,
    ),
    GarminConnectSensorEntityDescription(
        key="mediumStressDuration",
        translation_key="medium_stress_duration",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:timer-alert",
        value_fn=lambda data: round(data.get(
            "mediumStressDuration", 0) / 60, 2) if data.get("mediumStressDuration") else None,
    ),
    GarminConnectSensorEntityDescription(
        key="highStressDuration",
        translation_key="high_stress_duration",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:timer-remove",
        value_fn=lambda data: round(data.get(
            "highStressDuration", 0) / 60, 2) if data.get("highStressDuration") else None,
    ),
)

# Sleep Sensors
SLEEP_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="sleepingSeconds",
        translation_key="sleeping_time",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:sleep",
        value_fn=lambda data: round(data.get(
            "sleepingSeconds", 0) / 60, 2) if data.get("sleepingSeconds") else None,
    ),
    GarminConnectSensorEntityDescription(
        key="sleepTimeSeconds",
        translation_key="total_sleep_duration",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:sleep",
        value_fn=lambda data: round(data.get(
            "sleepTimeSeconds", 0) / 60, 2) if data.get("sleepTimeSeconds") else None,
    ),
    GarminConnectSensorEntityDescription(
        key="measurableAsleepDuration",
        translation_key="sleep_duration",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:sleep",
        value_fn=lambda data: round(data.get(
            "measurableAsleepDuration", 0) / 60, 2) if data.get("measurableAsleepDuration") else None,
    ),
    GarminConnectSensorEntityDescription(
        key="measurableAwakeDuration",
        translation_key="awake_duration",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:sleep-off",
        value_fn=lambda data: round(data.get(
            "measurableAwakeDuration", 0) / 60, 2) if data.get("measurableAwakeDuration") else None,
    ),
    GarminConnectSensorEntityDescription(
        key="sleepScore",
        translation_key="sleep_score",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:sleep",
    ),
    GarminConnectSensorEntityDescription(
        key="deepSleepSeconds",
        translation_key="deep_sleep",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:sleep",
        value_fn=lambda data: round(data.get(
            "deepSleepSeconds", 0) / 60, 2) if data.get("deepSleepSeconds") else None,
    ),
    GarminConnectSensorEntityDescription(
        key="lightSleepSeconds",
        translation_key="light_sleep",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:sleep",
        value_fn=lambda data: round(data.get(
            "lightSleepSeconds", 0) / 60, 2) if data.get("lightSleepSeconds") else None,
    ),
    GarminConnectSensorEntityDescription(
        key="remSleepSeconds",
        translation_key="rem_sleep",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:sleep",
        value_fn=lambda data: round(data.get(
            "remSleepSeconds", 0) / 60, 2) if data.get("remSleepSeconds") else None,
    ),
    GarminConnectSensorEntityDescription(
        key="awakeSleepSeconds",
        translation_key="awake_sleep",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:sleep-off",
        value_fn=lambda data: round(data.get(
            "awakeSleepSeconds", 0) / 60, 2) if data.get("awakeSleepSeconds") else None,
    ),
)

# Body Battery Sensors
BODY_BATTERY_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="bodyBatteryMostRecentValue",
        translation_key="body_battery_most_recent",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:battery-heart",
    ),
    GarminConnectSensorEntityDescription(
        key="bodyBatteryHighestValue",
        translation_key="body_battery_highest",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:battery-charging-100",
    ),
    GarminConnectSensorEntityDescription(
        key="bodyBatteryLowestValue",
        translation_key="body_battery_lowest",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:battery-heart-outline",
    ),
    GarminConnectSensorEntityDescription(
        key="bodyBatteryChargedValue",
        translation_key="body_battery_charged",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:battery-plus",
    ),
    GarminConnectSensorEntityDescription(
        key="bodyBatteryDrainedValue",
        translation_key="body_battery_drained",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:battery-minus",
    ),
)

# Body Composition Sensors
BODY_COMPOSITION_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="weight",
        translation_key="weight",
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        icon="mdi:weight-kilogram",
        value_fn=lambda data: round(
            data.get("weight", 0) / 1000, 2) if data.get("weight") else None,
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="bmi",
        translation_key="bmi",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="BMI",
        icon="mdi:human",
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="bodyFat",
        translation_key="body_fat",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:percent",
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="bodyWater",
        translation_key="body_water",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:water-percent",
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="boneMass",
        translation_key="bone_mass",
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        icon="mdi:bone",
        value_fn=lambda data: round(
            data.get("boneMass", 0) / 1000, 2) if data.get("boneMass") else None,
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="muscleMass",
        translation_key="muscle_mass",
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        icon="mdi:dumbbell",
        value_fn=lambda data: round(
            data.get("muscleMass", 0) / 1000, 2) if data.get("muscleMass") else None,
        preserve_value=True,
    ),
)

# Hydration Sensors
HYDRATION_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="valueInML",
        translation_key="hydration",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolume.MILLILITERS,
        icon="mdi:water",
    ),
    GarminConnectSensorEntityDescription(
        key="goalInML",
        translation_key="hydration_goal",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolume.MILLILITERS,
        icon="mdi:water-check",
    ),
    GarminConnectSensorEntityDescription(
        key="dailyAverageInML",
        translation_key="hydration_daily_average",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolume.MILLILITERS,
        icon="mdi:water-sync",
    ),
    GarminConnectSensorEntityDescription(
        key="sweatLossInML",
        translation_key="hydration_sweat_loss",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolume.MILLILITERS,
        icon="mdi:water-minus",
    ),
    GarminConnectSensorEntityDescription(
        key="activityIntakeInML",
        translation_key="hydration_activity_intake",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolume.MILLILITERS,
        icon="mdi:water-plus",
    ),
)

# Intensity & Activity Time Sensors
INTENSITY_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="activeSeconds",
        translation_key="active_time",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:fire",
        value_fn=lambda data: round(
            data.get("activeSeconds", 0) / 60, 2) if data.get("activeSeconds") else None,
    ),
    GarminConnectSensorEntityDescription(
        key="highlyActiveSeconds",
        translation_key="highly_active_time",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:fire",
        value_fn=lambda data: round(data.get(
            "highlyActiveSeconds", 0) / 60, 2) if data.get("highlyActiveSeconds") else None,

    ),
    GarminConnectSensorEntityDescription(
        key="sedentarySeconds",
        translation_key="sedentary_time",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:seat",
        value_fn=lambda data: round(data.get(
            "sedentarySeconds", 0) / 60, 2) if data.get("sedentarySeconds") else None,
    ),
    GarminConnectSensorEntityDescription(
        key="moderateIntensityMinutes",
        translation_key="moderate_intensity",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:flash-alert",

    ),
    GarminConnectSensorEntityDescription(
        key="vigorousIntensityMinutes",
        translation_key="vigorous_intensity",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:run-fast",

    ),
    GarminConnectSensorEntityDescription(
        key="intensityMinutesGoal",
        translation_key="intensity_goal",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:target",

    ),
)

# SPO2 & Respiration Sensors
HEALTH_MONITORING_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="averageSpo2",
        translation_key="avg_spo2",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:diabetes",
    ),
    GarminConnectSensorEntityDescription(
        key="lowestSpo2",
        translation_key="lowest_spo2",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:diabetes",
    ),
    GarminConnectSensorEntityDescription(
        key="latestSpo2",
        translation_key="latest_spo2",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:diabetes",
    ),
    GarminConnectSensorEntityDescription(
        key="latestSpo2ReadingTimeLocal",
        translation_key="latest_spo2_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock",

    ),
    GarminConnectSensorEntityDescription(
        key="highestRespirationValue",
        translation_key="highest_respiration",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="brpm",
        icon="mdi:progress-clock",

    ),
    GarminConnectSensorEntityDescription(
        key="lowestRespirationValue",
        translation_key="lowest_respiration",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="brpm",
        icon="mdi:progress-clock",

    ),
    GarminConnectSensorEntityDescription(
        key="latestRespirationValue",
        translation_key="latest_respiration",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="brpm",
        icon="mdi:progress-clock",

    ),
    GarminConnectSensorEntityDescription(
        key="latestRespirationTimeGMT",
        translation_key="latest_respiration_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock",

    ),
    GarminConnectSensorEntityDescription(
        key="averageMonitoringEnvironmentAltitude",
        translation_key="avg_altitude",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:image-filter-hdr",

    ),
)

# Fitness Age & Performance Sensors
FITNESS_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="chronologicalAge",
        translation_key="chronological_age",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.YEARS,
        icon="mdi:calendar-heart",
    ),
    GarminConnectSensorEntityDescription(
        key="fitnessAge",
        translation_key="fitness_age",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.YEARS,
        icon="mdi:calendar-heart",
    ),
    GarminConnectSensorEntityDescription(
        key="achievableFitnessAge",
        translation_key="achievable_fitness_age",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.YEARS,
        icon="mdi:calendar-heart",
    ),
    GarminConnectSensorEntityDescription(
        key="previousFitnessAge",
        translation_key="previous_fitness_age",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.YEARS,
        icon="mdi:calendar-heart",
    ),
    GarminConnectSensorEntityDescription(
        key="metabolicAge",
        translation_key="metabolic_age",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.YEARS,
        icon="mdi:calendar-heart",
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="enduranceScore",
        translation_key="endurance_score",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:run",

        value_fn=lambda data: data.get("enduranceScore", {}).get("overallScore"),
        attributes_fn=lambda data: {
            **{k: v for k, v in data.get("enduranceScore", {}).items() if k != "overallScore"},
        },
    ),
    GarminConnectSensorEntityDescription(
        key="hillScore",
        translation_key="hill_score",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:terrain",
        value_fn=lambda data: data.get("hillScore", {}).get("overallScore"),
        attributes_fn=lambda data: {
            **{k: v for k, v in data.get("hillScore", {}).items() if k != "overallScore"},
        },
    ),
    GarminConnectSensorEntityDescription(
        key="physiqueRating",
        translation_key="physique_rating",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:numeric",
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="visceralFat",
        translation_key="visceral_fat",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:food",
        preserve_value=True,
    ),
)

# Activity & Gamification Sensors
ACTIVITY_TRACKING_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="nextAlarm",
        translation_key="next_alarm",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:alarm",
        value_fn=lambda data: data.get("nextAlarm", [None])[0] if data.get("nextAlarm") else None,
        attributes_fn=lambda data: {

            "next_alarms": data.get("nextAlarm"),
        },
    ),
    GarminConnectSensorEntityDescription(
        key="lastActivity",
        translation_key="last_activity",
        icon="mdi:walk",

        value_fn=lambda data: data.get("lastActivity", {}).get("activityName"),
        attributes_fn=lambda data: _trim_activity(data.get("lastActivity", {})),
    ),
    GarminConnectSensorEntityDescription(
        key="lastActivities",
        translation_key="last_activities",
        state_class=SensorStateClass.TOTAL,
        icon="mdi:numeric",

        value_fn=lambda data: len(data.get("lastActivities", [])),
        attributes_fn=lambda data: {
            "last_activities": [
                _trim_activity(a) for a in sorted(
                    data.get("lastActivities", []),
                    key=lambda x: x.get("activityId", 0),
                )[-10:]
            ],
        },
    ),
    GarminConnectSensorEntityDescription(
        key="lastWorkout",
        translation_key="last_workout",
        icon="mdi:dumbbell",

        value_fn=lambda data: data.get("lastWorkout", {}).get("workoutName"),
        attributes_fn=lambda data: data.get("lastWorkout", {}),
    ),
    GarminConnectSensorEntityDescription(
        key="lastWorkouts",
        translation_key="last_workouts",
        state_class=SensorStateClass.TOTAL,
        icon="mdi:dumbbell",

        value_fn=lambda data: len(data.get("workouts", [])),
        attributes_fn=lambda data: {
            "last_workouts": data.get("workouts", [])[-10:],
        },
    ),
    GarminConnectSensorEntityDescription(
        key="trainingReadiness",
        translation_key="training_readiness",
        icon="mdi:run-fast",
        native_unit_of_measurement=PERCENTAGE,

        value_fn=lambda data: data.get("trainingReadiness", {}).get("score")
        if isinstance(data.get("trainingReadiness"), dict)
        else (data.get("trainingReadiness", [{}])[0].get("score")
              if isinstance(data.get("trainingReadiness"), list) and data.get("trainingReadiness")
              else None),
        attributes_fn=lambda data: data.get("trainingReadiness", {})
        if isinstance(data.get("trainingReadiness"), dict)
        else (data.get("trainingReadiness", [{}])[0]
              if isinstance(data.get("trainingReadiness"), list) and data.get("trainingReadiness")
              else {}),
    ),
    GarminConnectSensorEntityDescription(
        key="trainingStatus",
        translation_key="training_status",
        icon="mdi:chart-line",

        value_fn=lambda data: data.get("trainingStatus", {}).get("trainingStatusPhrase"),
        attributes_fn=lambda data: data.get("trainingStatus", {}),
    ),
    GarminConnectSensorEntityDescription(
        key="lactateThresholdHeartRate",
        translation_key="lactate_threshold_hr",
        icon="mdi:heart-pulse",
        native_unit_of_measurement="bpm",

        value_fn=lambda data: data.get("lactateThreshold", {}).get(
            "speed_and_heart_rate", {}
        ).get("heartRate"),
        attributes_fn=lambda data: data.get("lactateThreshold", {}),
    ),
    GarminConnectSensorEntityDescription(
        key="lactateThresholdSpeed",
        translation_key="lactate_threshold_speed",
        icon="mdi:speedometer",
        native_unit_of_measurement="m/s",

        value_fn=lambda data: data.get("lactateThreshold", {}).get(
            "speed_and_heart_rate", {}
        ).get("speed"),
        attributes_fn=lambda data: data.get("lactateThreshold", {}),
    ),
    GarminConnectSensorEntityDescription(
        key="badges",
        translation_key="badges",
        state_class=SensorStateClass.TOTAL,
        icon="mdi:medal",

        value_fn=lambda data: len(data.get("badges", [])),
        attributes_fn=lambda data: {

            "badges": sorted(
                data.get("badges", []),
                key=lambda x: x.get("badgeEarnedDate", ""),
            )[-10:],
        },
    ),
    GarminConnectSensorEntityDescription(
        key="userPoints",
        translation_key="user_points",
        state_class=SensorStateClass.TOTAL,
        icon="mdi:counter",

    ),
    GarminConnectSensorEntityDescription(
        key="userLevel",
        translation_key="user_level",
        state_class=SensorStateClass.TOTAL,
        icon="mdi:star-four-points-circle",

    ),
)

# Additional Heart Rate Sensors (less common)
ADDITIONAL_HEART_RATE_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="minAvgHeartRate",
        translation_key="min_avg_heart_rate",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="bpm",
        icon="mdi:heart-pulse",

    ),
    GarminConnectSensorEntityDescription(
        key="maxAvgHeartRate",
        translation_key="max_avg_heart_rate",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="bpm",
        icon="mdi:heart-pulse",

    ),
    GarminConnectSensorEntityDescription(
        key="abnormalHeartRateAlertsCount",
        translation_key="abnormal_hr_alerts",
        state_class=SensorStateClass.TOTAL,
        icon="mdi:heart-pulse",

    ),
)

# Additional stress percentage sensors (disabled by default - less useful)
STRESS_PERCENTAGE_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="stressPercentage",
        translation_key="stress_percentage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:flash-alert",

    ),
    GarminConnectSensorEntityDescription(
        key="restStressPercentage",
        translation_key="rest_stress_percentage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:flash-alert",

    ),
    GarminConnectSensorEntityDescription(
        key="activityStressPercentage",
        translation_key="activity_stress_percentage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:flash-alert",

    ),
    GarminConnectSensorEntityDescription(
        key="uncategorizedStressPercentage",
        translation_key="uncategorized_stress_percentage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:flash-alert",

    ),
    GarminConnectSensorEntityDescription(
        key="lowStressPercentage",
        translation_key="low_stress_percentage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:flash-alert",

    ),
    GarminConnectSensorEntityDescription(
        key="mediumStressPercentage",
        translation_key="medium_stress_percentage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:flash-alert",

    ),
    GarminConnectSensorEntityDescription(
        key="highStressPercentage",
        translation_key="high_stress_percentage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:flash-alert",

    ),
)

# Additional stress duration sensor
ADDITIONAL_STRESS_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="uncategorizedStressDuration",
        translation_key="uncategorized_stress_duration",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:flash-alert",
        value_fn=lambda data: round(data.get(
            "uncategorizedStressDuration", 0) / 60, 2) if data.get("uncategorizedStressDuration") else None,
    ),
    GarminConnectSensorEntityDescription(
        key="stressDuration",
        translation_key="stress_duration",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:flash-alert",
        value_fn=lambda data: round(
            data.get("stressDuration", 0) / 60, 2) if data.get("stressDuration") else None,

    ),
)

# Additional distance sensors (meters variants - disabled by default)
ADDITIONAL_DISTANCE_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="floorsAscendedInMeters",
        translation_key="floors_ascended_meters",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfLength.METERS,
        icon="mdi:stairs-up",

    ),
    GarminConnectSensorEntityDescription(
        key="floorsDescendedInMeters",
        translation_key="floors_descended_meters",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfLength.METERS,
        icon="mdi:stairs-down",

    ),
)

# Wellness sensors (disabled by default - typically not used)
WELLNESS_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="wellnessStartTimeLocal",
        translation_key="wellness_start_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock",

    ),
    GarminConnectSensorEntityDescription(
        key="wellnessEndTimeLocal",
        translation_key="wellness_end_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock",

    ),
    GarminConnectSensorEntityDescription(
        key="wellnessDescription",
        translation_key="wellness_description",
        state_class=SensorStateClass.TOTAL,
        icon="mdi:text",

    ),
    GarminConnectSensorEntityDescription(
        key="wellnessDistanceMeters",
        translation_key="wellness_distance",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfLength.METERS,
        icon="mdi:walk",

    ),
    GarminConnectSensorEntityDescription(
        key="wellnessActiveKilocalories",
        translation_key="wellness_active_calories",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kcal",
        icon="mdi:fire",

    ),
    GarminConnectSensorEntityDescription(
        key="wellnessKilocalories",
        translation_key="wellness_calories",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kcal",
        icon="mdi:fire",

    ),
)

# All sensor descriptions grouped
# Menstrual Cycle Sensors
MENSTRUAL_CYCLE_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="menstrualCyclePhase",
        translation_key="menstrual_cycle_phase",
        icon="mdi:calendar-heart",
        value_fn=lambda data: data.get("menstrualData", {}).get("currentPhase"),
        attributes_fn=lambda data: {

            **{k: v for k, v in data.get("menstrualData", {}).items()
               if k not in ("currentPhase",)},
        },
    ),
    GarminConnectSensorEntityDescription(
        key="menstrualCycleDay",
        translation_key="menstrual_cycle_day",
        icon="mdi:calendar-today",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("menstrualData", {}).get("dayOfCycle"),
        attributes_fn=lambda data: {

        },
    ),
    GarminConnectSensorEntityDescription(
        key="menstrualPeriodDay",
        translation_key="menstrual_period_day",
        icon="mdi:water",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("menstrualData", {}).get("dayOfPeriod"),
        attributes_fn=lambda data: {

        },
    ),
    GarminConnectSensorEntityDescription(
        key="menstrualCycleLength",
        translation_key="menstrual_cycle_length",
        icon="mdi:calendar-range",
        native_unit_of_measurement=UnitOfTime.DAYS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("menstrualData", {}).get("cycleLength"),
        attributes_fn=lambda data: {

        },
    ),
    GarminConnectSensorEntityDescription(
        key="menstrualPeriodLength",
        translation_key="menstrual_period_length",
        icon="mdi:calendar-clock",
        native_unit_of_measurement=UnitOfTime.DAYS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("menstrualData", {}).get("periodLength"),
        attributes_fn=lambda data: {

        },
    ),
)

# Blood Pressure Sensors
BLOOD_PRESSURE_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="bpSystolic",
        translation_key="bp_systolic",
        native_unit_of_measurement="mmHg",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:heart-pulse",
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="bpDiastolic",
        translation_key="bp_diastolic",
        native_unit_of_measurement="mmHg",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:heart-pulse",
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="bpPulse",
        translation_key="bp_pulse",
        native_unit_of_measurement="bpm",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:heart",
        preserve_value=True,
    ),
    GarminConnectSensorEntityDescription(
        key="bpMeasurementTime",
        translation_key="bp_measurement_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock-outline",
        value_fn=lambda data: data.get("bpMeasurementTime"),
        preserve_value=True,
    ),
)

# Diagnostic Sensors
DIAGNOSTIC_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="lastSyncTimestampGMT",
        translation_key="device_last_synced",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:sync",
        # Value is already an ISO timestamp string, just pass it through
        value_fn=lambda data: data.get("lastSyncTimestampGMT"),
    ),
)

ALL_SENSOR_DESCRIPTIONS: tuple[GarminConnectSensorEntityDescription, ...] = (
    *ACTIVITY_SENSORS,
    *CALORIES_SENSORS,
    *HEART_RATE_SENSORS,
    *ADDITIONAL_HEART_RATE_SENSORS,
    *STRESS_SENSORS,
    *ADDITIONAL_STRESS_SENSORS,
    *STRESS_PERCENTAGE_SENSORS,
    *SLEEP_SENSORS,
    *BODY_BATTERY_SENSORS,
    *BODY_COMPOSITION_SENSORS,
    *HYDRATION_SENSORS,
    *INTENSITY_SENSORS,
    *HEALTH_MONITORING_SENSORS,
    *FITNESS_SENSORS,
    *ACTIVITY_TRACKING_SENSORS,
    *ADDITIONAL_DISTANCE_SENSORS,
    *WELLNESS_SENSORS,
    *MENSTRUAL_CYCLE_SENSORS,
    *BLOOD_PRESSURE_SENSORS,
    *DIAGNOSTIC_SENSORS,
)




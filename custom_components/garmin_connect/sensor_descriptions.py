"""Sensor entity descriptions for Garmin Connect integration."""

from dataclasses import dataclass
from collections.abc import Callable
from typing import Any, NamedTuple

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


@dataclass(frozen=True, kw_only=True)
class GarminConnectSensorEntityDescription(SensorEntityDescription):
    """Describes Garmin Connect sensor entity."""

    value_fn: Callable[[dict[str, Any]], Any] | None = None
    """Function to extract value from coordinator data."""

    attributes_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None
    """Function to extract attributes from coordinator data."""


class SensorGroup(NamedTuple):
    """Definition of a sensor group."""

    name: str
    """Display name of the sensor group."""

    description: str
    """Description of what sensors are in this group."""

    enabled_by_default: bool = True
    """Whether this group should be enabled by default."""


# Sensor group definitions for configuration
SENSOR_GROUPS: dict[str, SensorGroup] = {
    "activity": SensorGroup(
        "Activity & Steps",
        "Step counts, distance, floors climbed, and daily goals",
        True,
    ),
    "calories": SensorGroup(
        "Calories & Nutrition",
        "Calorie tracking including active, burned, consumed, and remaining",
        True,
    ),
    "heart_rate": SensorGroup(
        "Heart Rate",
        "Heart rate monitoring including resting, min/max, and HRV status",
        True,
    ),
    "stress": SensorGroup(
        "Stress",
        "Stress levels and duration tracking",
        True,
    ),
    "sleep": SensorGroup(
        "Sleep",
        "Sleep duration, quality scores, and sleep stages",
        True,
    ),
    "body_battery": SensorGroup(
        "Body Battery",
        "Garmin Body Battery energy monitoring",
        True,
    ),
    "body_composition": SensorGroup(
        "Body Composition",
        "Weight, BMI, body fat, muscle mass, and bone mass",
        False,  # Disabled by default - requires compatible scale
    ),
    "hydration": SensorGroup(
        "Hydration",
        "Water intake tracking and hydration goals",
        True,
    ),
    "intensity": SensorGroup(
        "Intensity & Activity Time",
        "Active time, sedentary time, and intensity minutes",
        True,
    ),
    "health_monitoring": SensorGroup(
        "Health Monitoring",
        "SpO2 (blood oxygen), respiration rate, and altitude",
        True,
    ),
    "fitness": SensorGroup(
        "Fitness & Performance",
        "Fitness age, endurance score, and metabolic age",
        True,
    ),
    "activity_tracking": SensorGroup(
        "Activity Tracking",
        "Recent activities, badges, points, and gamification",
        False,  # Disabled by default - less commonly used
    ),
    "advanced": SensorGroup(
        "Advanced Sensors",
        "Additional detailed metrics and alternative measurements",
        False,  # Disabled by default - advanced/redundant sensors
    ),
}


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
        entity_category=EntityCategory.DIAGNOSTIC,
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
        entity_category=EntityCategory.DIAGNOSTIC,
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
        entity_category=EntityCategory.DIAGNOSTIC,
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
        entity_registry_enabled_default=False,
    ),
    GarminConnectSensorEntityDescription(
        key="remainingKilocalories",
        translation_key="remaining_calories",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kcal",
        icon="mdi:food",
        entity_registry_enabled_default=False,
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
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
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
        entity_registry_enabled_default=False,
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
        entity_registry_enabled_default=False,
    ),
    GarminConnectSensorEntityDescription(
        key="bmi",
        translation_key="bmi",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="BMI",
        icon="mdi:human",
        entity_registry_enabled_default=False,
    ),
    GarminConnectSensorEntityDescription(
        key="bodyFat",
        translation_key="body_fat",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:percent",
        entity_registry_enabled_default=False,
    ),
    GarminConnectSensorEntityDescription(
        key="bodyWater",
        translation_key="body_water",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:water-percent",
        entity_registry_enabled_default=False,
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
        entity_registry_enabled_default=False,
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
        entity_registry_enabled_default=False,
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
        entity_category=EntityCategory.DIAGNOSTIC,
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
        entity_registry_enabled_default=False,
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
        entity_registry_enabled_default=False,
    ),
    GarminConnectSensorEntityDescription(
        key="vigorousIntensityMinutes",
        translation_key="vigorous_intensity",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:run-fast",
        entity_registry_enabled_default=False,
    ),
    GarminConnectSensorEntityDescription(
        key="intensityMinutesGoal",
        translation_key="intensity_goal",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:target",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
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
        entity_registry_enabled_default=False,
    ),
    GarminConnectSensorEntityDescription(
        key="highestRespirationValue",
        translation_key="highest_respiration",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="brpm",
        icon="mdi:progress-clock",
        entity_registry_enabled_default=False,
    ),
    GarminConnectSensorEntityDescription(
        key="lowestRespirationValue",
        translation_key="lowest_respiration",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="brpm",
        icon="mdi:progress-clock",
        entity_registry_enabled_default=False,
    ),
    GarminConnectSensorEntityDescription(
        key="latestRespirationValue",
        translation_key="latest_respiration",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="brpm",
        icon="mdi:progress-clock",
        entity_registry_enabled_default=False,
    ),
    GarminConnectSensorEntityDescription(
        key="latestRespirationTimeGMT",
        translation_key="latest_respiration_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock",
        entity_registry_enabled_default=False,
    ),
    GarminConnectSensorEntityDescription(
        key="averageMonitoringEnvironmentAltitude",
        translation_key="avg_altitude",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:image-filter-hdr",
        entity_registry_enabled_default=False,
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
        entity_registry_enabled_default=False,
    ),
    GarminConnectSensorEntityDescription(
        key="enduranceScore",
        translation_key="endurance_score",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:run",
        entity_registry_enabled_default=False,
    ),
    GarminConnectSensorEntityDescription(
        key="physiqueRating",
        translation_key="physique_rating",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:numeric",
        entity_registry_enabled_default=False,
    ),
    GarminConnectSensorEntityDescription(
        key="visceralFat",
        translation_key="visceral_fat",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:food",
        entity_registry_enabled_default=False,
    ),
)

# Activity & Gamification Sensors
ACTIVITY_TRACKING_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="nextAlarm",
        translation_key="next_alarm",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:alarm",
    ),
    GarminConnectSensorEntityDescription(
        key="lastActivity",
        translation_key="last_activity",
        icon="mdi:walk",
        entity_registry_enabled_default=False,
    ),
    GarminConnectSensorEntityDescription(
        key="lastActivities",
        translation_key="last_activities",
        state_class=SensorStateClass.TOTAL,
        icon="mdi:numeric",
        entity_registry_enabled_default=False,
    ),
    GarminConnectSensorEntityDescription(
        key="badges",
        translation_key="badges",
        state_class=SensorStateClass.TOTAL,
        icon="mdi:medal",
        entity_registry_enabled_default=False,
    ),
    GarminConnectSensorEntityDescription(
        key="userPoints",
        translation_key="user_points",
        state_class=SensorStateClass.TOTAL,
        icon="mdi:counter",
        entity_registry_enabled_default=False,
    ),
    GarminConnectSensorEntityDescription(
        key="userLevel",
        translation_key="user_level",
        state_class=SensorStateClass.TOTAL,
        icon="mdi:star-four-points-circle",
        entity_registry_enabled_default=False,
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
        entity_registry_enabled_default=False,
    ),
    GarminConnectSensorEntityDescription(
        key="maxAvgHeartRate",
        translation_key="max_avg_heart_rate",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="bpm",
        icon="mdi:heart-pulse",
        entity_registry_enabled_default=False,
    ),
    GarminConnectSensorEntityDescription(
        key="abnormalHeartRateAlertsCount",
        translation_key="abnormal_hr_alerts",
        state_class=SensorStateClass.TOTAL,
        icon="mdi:heart-pulse",
        entity_registry_enabled_default=False,
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
        entity_registry_enabled_default=False,
    ),
    GarminConnectSensorEntityDescription(
        key="restStressPercentage",
        translation_key="rest_stress_percentage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:flash-alert",
        entity_registry_enabled_default=False,
    ),
    GarminConnectSensorEntityDescription(
        key="activityStressPercentage",
        translation_key="activity_stress_percentage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:flash-alert",
        entity_registry_enabled_default=False,
    ),
    GarminConnectSensorEntityDescription(
        key="uncategorizedStressPercentage",
        translation_key="uncategorized_stress_percentage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:flash-alert",
        entity_registry_enabled_default=False,
    ),
    GarminConnectSensorEntityDescription(
        key="lowStressPercentage",
        translation_key="low_stress_percentage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:flash-alert",
        entity_registry_enabled_default=False,
    ),
    GarminConnectSensorEntityDescription(
        key="mediumStressPercentage",
        translation_key="medium_stress_percentage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:flash-alert",
        entity_registry_enabled_default=False,
    ),
    GarminConnectSensorEntityDescription(
        key="highStressPercentage",
        translation_key="high_stress_percentage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:flash-alert",
        entity_registry_enabled_default=False,
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
        entity_registry_enabled_default=False,
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
        entity_registry_enabled_default=False,
    ),
    GarminConnectSensorEntityDescription(
        key="floorsDescendedInMeters",
        translation_key="floors_descended_meters",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfLength.METERS,
        icon="mdi:stairs-down",
        entity_registry_enabled_default=False,
    ),
)

# Wellness sensors (disabled by default - typically not used)
WELLNESS_SENSORS: tuple[GarminConnectSensorEntityDescription, ...] = (
    GarminConnectSensorEntityDescription(
        key="wellnessStartTimeLocal",
        translation_key="wellness_start_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock",
        entity_registry_enabled_default=False,
    ),
    GarminConnectSensorEntityDescription(
        key="wellnessEndTimeLocal",
        translation_key="wellness_end_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock",
        entity_registry_enabled_default=False,
    ),
    GarminConnectSensorEntityDescription(
        key="wellnessDescription",
        translation_key="wellness_description",
        state_class=SensorStateClass.TOTAL,
        icon="mdi:text",
        entity_registry_enabled_default=False,
    ),
    GarminConnectSensorEntityDescription(
        key="wellnessDistanceMeters",
        translation_key="wellness_distance",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfLength.METERS,
        icon="mdi:walk",
        entity_registry_enabled_default=False,
    ),
    GarminConnectSensorEntityDescription(
        key="wellnessActiveKilocalories",
        translation_key="wellness_active_calories",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kcal",
        icon="mdi:fire",
        entity_registry_enabled_default=False,
    ),
    GarminConnectSensorEntityDescription(
        key="wellnessKilocalories",
        translation_key="wellness_calories",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kcal",
        icon="mdi:fire",
        entity_registry_enabled_default=False,
    ),
)

# All sensor descriptions grouped
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
)


# Mapping of sensor groups to their sensor tuples
SENSOR_GROUP_MAPPING: dict[str, tuple[GarminConnectSensorEntityDescription, ...]] = {
    "activity": ACTIVITY_SENSORS,
    "calories": CALORIES_SENSORS,
    "heart_rate": HEART_RATE_SENSORS,
    "stress": STRESS_SENSORS,
    "sleep": SLEEP_SENSORS,
    "body_battery": BODY_BATTERY_SENSORS,
    "body_composition": BODY_COMPOSITION_SENSORS,
    "hydration": HYDRATION_SENSORS,
    "intensity": INTENSITY_SENSORS,
    "health_monitoring": HEALTH_MONITORING_SENSORS,
    "fitness": FITNESS_SENSORS,
    "activity_tracking": ACTIVITY_TRACKING_SENSORS,
    "advanced": (
        *ADDITIONAL_HEART_RATE_SENSORS,
        *ADDITIONAL_STRESS_SENSORS,
        *STRESS_PERCENTAGE_SENSORS,
        *ADDITIONAL_DISTANCE_SENSORS,
        *WELLNESS_SENSORS,
    ),
}


def get_sensors_for_groups(
    enabled_groups: set[str] | None = None,
) -> tuple[GarminConnectSensorEntityDescription, ...]:
    """Get sensor descriptions based on enabled sensor groups.

    Args:
        enabled_groups: Set of enabled group IDs. If None, returns all sensors.

    Returns:
        Tuple of sensor descriptions for the enabled groups.

    """
    if enabled_groups is None:
        return ALL_SENSOR_DESCRIPTIONS
    
    sensors = []
    for group_id in enabled_groups:
        if group_id in SENSOR_GROUP_MAPPING:
            sensors.extend(SENSOR_GROUP_MAPPING[group_id])
    
    return tuple(sensors)


def get_default_enabled_groups() -> set[str]:
    """Get the set of sensor groups that should be enabled by default.
    
    Returns:
        Set of group IDs that are enabled by default.

    """
    return {
        group_id
        for group_id, group in SENSOR_GROUPS.items()
        if group.enabled_by_default
    }


---
title: Garmin Connect
description: Instructions on how to integrate Garmin Connect health data within Home Assistant.
ha_category:
  - Health
  - Sensor
ha_iot_class: Cloud Polling
ha_release: "2025.2"
ha_domain: garmin_connect
ha_platforms:
  - sensor
ha_integration_type: integration
ha_codeowners:
  - '@cyberjunky'
ha_config_flow: true
---

The **Garmin Connect** {% term integration %} allows you to expose health and fitness data from [Garmin Connect](https://connect.garmin.com/) to Home Assistant.

## Prerequisites

You need a Garmin Connect account with at least one Garmin device that syncs data to Garmin Connect.

{% include integrations/config_flow.md %}

## Sensors

This integration provides **100+ sensors** covering various health and fitness metrics. Sensors are grouped into the following categories:

### Activity & Steps

- **Total Steps** - Daily step count
- **Daily Step Goal** - Your configured step target
- **Total Distance** - Distance walked/run
- **Floors Ascended/Descended** - Floors climbed

### Calories

- **Total Calories** - Total daily calorie burn
- **Active Calories** - Calories burned through activity
- **BMR Calories** - Basal metabolic rate calories

### Heart Rate

- **Resting Heart Rate** - Daily resting HR
- **Min/Max Heart Rate** - Daily HR range
- **Last 7 Days Avg HR** - Weekly average

### Stress & Recovery

- **Avg/Max Stress Level** - Stress measurements (0-100)
- **Stress Durations** - Time in rest/activity/low/medium/high stress

### Sleep

- **Sleep Score** - Overall sleep quality score
- **Sleep Duration** - Time asleep
- **Awake Duration** - Time awake during sleep

### Body Battery

- **Body Battery** - Current energy level (0-100)
- **Charged/Drained** - Energy gained/spent

### Body Composition

- **Weight** - Body weight
- **BMI** - Body Mass Index
- **Body Fat/Water** - Percentage measurements
- **Muscle/Bone Mass** - Mass measurements

### Hydration

- **Hydration** - Daily water intake
- **Hydration Goal** - Target intake
- **Sweat Loss** - Estimated fluid loss

### Health Monitoring

- **SpO2** - Blood oxygen levels (average, lowest, latest)
- **HRV Status** - Heart rate variability
- **Respiration Rate** - Breathing measurements

### Fitness & Performance

- **Fitness Age** - Estimated fitness age
- **Endurance Score** - Overall endurance rating

### Menstrual Cycle Tracking

- **Cycle Phase** - Current menstrual phase
- **Cycle Day** - Day of the current cycle
- **Period Day** - Day of the period
- **Cycle/Period Length** - Cycle and period lengths in days

> **Note:** Menstrual cycle sensors are only available if tracking is enabled in your Garmin Connect account.

### Gear Tracking

Gear sensors are dynamically created for each piece of equipment registered in Garmin Connect (shoes, bikes, etc.). They track total distance and usage statistics.

## Actions

### Add body composition

Add body composition metrics to Garmin Connect.

| Data attribute | Required | Description |
| ---------------------- | -------- | ----------- |
| `weight` | Yes | Weight in kilograms |
| `timestamp` | No | ISO format timestamp |
| `bmi` | No | Body Mass Index |
| `percent_fat` | No | Body fat percentage |
| `muscle_mass` | No | Muscle mass in kg |
| `bone_mass` | No | Bone mass in kg |
| `body_water` | No | Body water percentage |
| `physique_rating` | No | Physique rating (1-9) |
| `visceral_fat` | No | Visceral fat rating |
| `metabolic_age` | No | Metabolic age |

### Add blood pressure

Add blood pressure measurements to Garmin Connect.

| Data attribute | Required | Description |
| ---------------------- | -------- | ----------- |
| `systolic` | Yes | Systolic pressure (mmHg) |
| `diastolic` | Yes | Diastolic pressure (mmHg) |
| `pulse` | Yes | Pulse rate (bpm) |
| `timestamp` | No | ISO format timestamp |
| `notes` | No | Notes about the measurement |

### Set active gear

Set a gear item as the default for an activity type.

| Data attribute | Required | Description |
| ---------------------- | -------- | ----------- |
| `activity_type` | Yes | Activity type (e.g., running, cycling) |
| `setting` | Yes | Setting option (set as default, unset default, set this as default unset others) |

## Data updates

Data is polled from Garmin Connect every 5 minutes. Due to API rate limits, more frequent polling is not recommended.

## MFA Support

If your Garmin account has Multi-Factor Authentication (MFA) enabled, you will be prompted to enter your MFA code during setup.

## Known limitations

- Not all sensors will have data depending on your Garmin devices and connected apps.
- API rate limits may cause temporary unavailability during high-traffic periods.

[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/hacs/integration)  [![made-with-python](https://img.shields.io/badge/Made%20with-Python-1f425f.svg)](https://www.python.org/) [![Donate](https://img.shields.io/badge/Donate-PayPal-green.svg)](https://www.paypal.me/cyberjunkynl/)

# Garmin Connect
The Garmin Connect integration allows you to expose data from Garmin Connect to Home Assistant.

NOTE: This integration doesn't support 2FA on Garmin Connect yet (support is coming), so if you have enabled it -and want to keep it- this integration doesn't work, it will try to login repeatedly and generate lots of 2FA codes via email.
The change of adding support for it is unlikely since the Garmin Connect API is closed source, and will not be open for open-sourced projects.

## Installation

### HACS - Recommended
- Have [HACS](https://hacs.xyz) installed, this will allow you to easily manage and track updates.
- Inside HACS click 'Explore & download repositories'
- Search for 'Garmin Connect'.
- Click on found integration.
- Click Download this repository with HACS.
- Restart Home-Assistant.
- Follow configuration steps below.

### Manual
- Copy directory `custom_components/garmin_connect` to your `<config dir>/custom_components` directory.
- Restart Home-Assistant.
- Follow configuration steps below.

## Configuration

Adding Garmin Connect to your Home Assistant instance can be done via the integrations user interface.

- Browse to your Home Assistant instance.
- In the sidebar click on Configuration.
- From the configuration menu select: Integrations.
- In the bottom right, click on the Add Integration button.
- From the list, search and select “Garmin Connect”.
- Follow the instruction on screen to complete the set up

After successful set up a standard set of sensors are enabled. You can enable more if needed by using the Integrations page.

Please be aware that Garmin Connect has very low rate limits, max. once every ~5 minutes.

## Available Sensors

Not every sensor holds meaningful values, it depends on the tracking and health devices you use, or the apps you have connected.

Enabled by default:

```text
Total Steps
Daily Step Goal
Total KiloCalories
Active KiloCalories
BMR KiloCalories
Burned KiloCalories
Total Distance Mtr
Active Time
Sedentary Time
Sleeping Time
Awake Duration
Sleep Duration
Total Sleep Duration
Floors Ascended
Floors Descended
Floors Ascended Goal
Min Heart Rate
Max Heart Rate
Resting Heart Rate
Avg Stress Level
Max Stress Level
Rest Stress Duration
Activity Stress Duration
Uncat. Stress Duration
Total Stress Duration
Low Stress Duration
Medium Stress Duration
High Stress Duration
Body Battery Charged
Body Battery Drained
Body Battery Highest
Body Battery Lowest
Body Battery Most Recent
Average SPO2
Lowest SPO2
Latest SPO2
Next Alarm Time
Total Sleep Duration
HRV Status
Gear Sensors
```

Disabled by default:

```text
Badges
User Points
User Level
Consumed KiloCalories
Remaining KiloCalories
Net Remaining KiloCalories
Net Calorie Goal
Wellness Start Time
Wellness End Time
Wellness Description
Wellness Distance Mtr
Wellness Active KiloCalories
Wellness KiloCalories
Highly Active Time
Floors Ascended Mtr
Floors Descended Mtr
Min Avg Heart Rate
Max Avg Heart Rate
Abnormal HR Counts
Last 7 Days Avg Heart Rate
Stress Qualifier
Stress Duration
Stress Percentage
Rest Stress Percentage
Activity Stress Percentage
Uncat. Stress Percentage
Low Stress Percentage
Medium Stress Percentage
High Stress Percentage
Latest SPO2 Time
Average Altitude
Moderate Intensity
Vigorous Intensity
Intensity Goal
Latest Respiration Update
Highest Respiration
Lowest Respiration
Latest Respiration
Weight
BMI
Body Fat
Body Water
Bone Mass
Muscle Mass
Physique Rating
Visceral Fat
Metabolic Age
Last Activities
Last Activity
```

## Screenshots

![screenshot](https://github.com/cyberjunky/home-assistant-garmin_connect/blob/main/screenshots/garmin_connect.png?raw=true "Screenshot Garmin Connect")

## Tips and Tricks

### Set up an automation using the garmin_connect.add_body_composition service

Useful if you want to pass your weight from another (incompatible) device to Garmin Connect. Garmin Connect does not calculate your BMI when you enter your weight manually so it needs to be passed along for now.

```
alias: uiSendWeightToGarminConnect
description: ""
trigger:
  - platform: state
    entity_id:
      - sensor.weight
condition:
  - condition: and
    conditions:
      - condition: numeric_state
        entity_id: sensor.weight
        above: 75
      - condition: numeric_state
        entity_id: sensor.weight
        below: 88
action:
  - service: garmin_connect.add_body_composition
    data:
      entity_id: sensor.weight
      weight: "{{trigger.to_state.state}}"
      timestamp: "{{ as_timestamp(now())  | timestamp_local}}"
      bmi: >-
        {{ (trigger.to_state.state | float(0) / 1.86**2 )| round(1, default=0)
        }}
mode: single
```

### Examples on how to test actions from HA GUI

#### Add Body Composition

```
action: garmin_connect.add_body_composition
data:
  entity_id: sensor.weight
  weight: 87
  bmi: 25.5
  bone_mass: 4.8
  ...
```

NOTE: You need to enable Weight entity

#### Set Active Gear

```
action: garmin_connect.set_active_gear
data:
  entity_id: sensor.adidas
  activity_type: running
  setting: set as default
```

#### Add Blood Pressure

```
action: garmin_connect.add_blood_pressure
data:
  entity_id: sensor.min_heart_rate
  systolic: 120
  diastolic: 80
  pulse: 60
  timestamp: 2025-1-21T07:34:00.000Z
  notes: Measured with Beurer BC54
```

## Debugging

Add the relevant lines below to the `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.garmin_connect: debug
```

## Donation
[![Donate](https://img.shields.io/badge/Donate-PayPal-green.svg)](https://www.paypal.me/cyberjunkynl/)

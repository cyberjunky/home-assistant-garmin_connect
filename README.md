[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)
![Project Maintenance][maintenance-shield]

[![Donate via PayPal](https://img.shields.io/badge/Donate-PayPal-blue.svg?style=for-the-badge&logo=paypal)](https://www.paypal.me/cyberjunkynl/)
[![Sponsor on GitHub](https://img.shields.io/badge/Sponsor-GitHub-red.svg?style=for-the-badge&logo=github)](https://github.com/sponsors/cyberjunky)

# Garmin Connect
The Garmin Connect integration allows you to expose data from Garmin Connect to Home Assistant.

## Install via HACS

- The installation is done inside [HACS](https://hacs.xyz/) (Home Assistant Community Store).
- If you already have HACS installed click on the MyHomeAssistant button below, otherwise install HACS before adding this integration.  
  You can find installation instructions [here.](https://hacs.xyz/docs/setup/download)
- Once HACS is installed, search for `garmin connect` and click on "Download". Once downloaded, restart HomeAssistant.

## 📦 Installation

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=cyberjunky&repository=home-assistant-garmin_connect&category=integration)

## Configuration

- In the sidebar, click 'Configuration', then 'Devices & Services'. Click the + icon to add "Garmin Connect" to your Home Assistant installation.
  - Enter the credentials of the Garmin Connect account you want to add.
  - Optionally -when MFA is enabled- it will ask for your MFA code.

After successful set up a standard set of sensors are enabled. You can enable more if needed by using the Entities page under Devices and services. (Filter on disabled state)

The integration will fetch new data every 5 minutes, make sure your devices sync to the Garmin Connect website.

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
Chronological Age
Fitness Age
Achievable Fitness Age
Previous Fitness Age
Hydration
Hydration Goal
Hydration Daily Average
Hydration Sweat Loss
Hydration Activity Intake
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
Endurance Score
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
```
See the action template for other available values to add

NOTE: You need to enable the Weight entity

Full example:
```
alias: WithingsToGarmin
description: ""
triggers:
  - trigger: state
    entity_id:
      - sensor.withings_poids
conditions:
  - condition: numeric_state
    entity_id: sensor.withings_poids
    above: 55
    below: 80
actions:
  - action: garmin_connect.add_body_composition
    metadata: {}
    data:
      entity_id: sensor.weight
      weight: "{{states('sensor.withings_poids')}}"
      timestamp: "{{ as_timestamp(now())  | timestamp_local}}"
      bmi: >-
        {{ (states('sensor.withings_poids') | float(0) / 1.72**2 )| round(1,
        default=0) }}
      bone_mass: "{{states('sensor.withings_bone_mass')}}"
      muscle_mass: "{{states('sensor.withings_masse_musculaire')}}"
      percent_hydration: >-
        {{ (float(states('sensor.withings_hydration')) /
        float(states('sensor.withings_poids')) * 100 ) | round(2, default=0) }}
      percent_fat: "{{states('sensor.withings_taux_de_graisse')}}"
mode: single
```

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

## 💖 Support This Project

If you find this library useful for your projects, please consider supporting its continued development and maintenance:

### 🌟 Ways to Support

- **⭐ Star this repository** - Help others discover the project
- **💰 Financial Support** - Contribute to development and hosting costs
- **🐛 Report Issues** - Help improve stability and compatibility
- **📖 Spread the Word** - Share with other developers

### 💳 Financial Support Options

[![Donate via PayPal](https://img.shields.io/badge/Donate-PayPal-blue.svg?style=for-the-badge&logo=paypal)](https://www.paypal.me/cyberjunkynl/)
[![Sponsor on GitHub](https://img.shields.io/badge/Sponsor-GitHub-red.svg?style=for-the-badge&logo=github)](https://github.com/sponsors/cyberjunky)

**Why Support?**
- Keeps the project actively maintained
- Enables faster bug fixes and new features
- Supports infrastructure costs (testing, AI, CI/CD)
- Shows appreciation for hundreds of hours of development

Every contribution, no matter the size, makes a difference and is greatly appreciated! 🙏

[releases-shield]: https://img.shields.io/github/release/cyberjunky/home-assistant-garmin_connect.svg?style=for-the-badge
[releases]: https://github.com/cyberjunky/home-assistant-garmin_connect/releases
[commits-shield]: https://img.shields.io/github/commit-activity/y/cyberjunky/home-assistant-garmin_connect.svg?style=for-the-badge
[commits]: https://github.com/cyberjunky/home-assistant-garmin_connect/commits/main
[license-shield]: https://img.shields.io/github/license/cyberjunky/home-assistant-garmin_connect.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-cyberjunky-blue.svg?style=for-the-badge

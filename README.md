[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs)  [![made-with-python](https://img.shields.io/badge/Made%20with-Python-1f425f.svg)](https://www.python.org/) [![Donate](https://img.shields.io/badge/Donate-PayPal-green.svg)](https://www.paypal.me/cyberjunkynl/)

# Garmin Connect
The Garmin Connect integration allows you to expose data from Garmin Connect to Home Assistant.


## Installation

### HACS - Recommended
- Have [HACS](https://hacs.xyz) installed, this will allow you to easily manage and track updates.
- Add https://github.com/cyberjunky/home-assistant-garmin_connect to custom repositories in HACS 
- Search for 'Garmin Connect'.
- Click Install below the found integration.
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
Consumed KiloCalories
Burned KiloCalories
Total Distance Mtr
Active Time
Sedentary Time
Sleeping Time
Awake Duration
Sleep Duration
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
```

Disabled by default:

```text
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
Body Mass
Muscle Mass
Physique Rating
Visceral Fat
Metabolic Age
```

## Screenshots

![screenshot](https://github.com/cyberjunky/home-assistant-garmin_connect/blob/main/screenshots/garmin_connect.png?raw=true "Screenshot Garmin Connect")

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

# Sensor Groups Feature

## Overview

The Garmin Connect integration now supports organizing sensors into logical groups that can be enabled or disabled together. This helps reduce clutter in your Home Assistant instance by only showing the sensors you actually use.

## Available Sensor Groups

### Enabled by Default

- **Activity & Steps**: Step counts, distance, floors climbed, and daily goals
- **Calories & Nutrition**: Calorie tracking including active, burned, consumed, and remaining
- **Heart Rate**: Heart rate monitoring including resting, min/max, and HRV status
- **Stress**: Stress levels and duration tracking
- **Sleep**: Sleep duration, quality scores, and sleep stages
- **Body Battery**: Garmin Body Battery energy monitoring
- **Hydration**: Water intake tracking and hydration goals
- **Intensity & Activity Time**: Active time, sedentary time, and intensity minutes
- **Health Monitoring**: SpO2 (blood oxygen), respiration rate, and altitude
- **Fitness & Performance**: Fitness age, endurance score, and metabolic age

### Disabled by Default

- **Body Composition**: Weight, BMI, body fat, muscle mass, and bone mass (requires compatible scale)
- **Activity Tracking**: Recent activities, badges, points, and gamification
- **Advanced Sensors**: Additional detailed metrics and alternative measurements

## How to Configure

### Initial Setup

When you first install the integration, all default sensor groups are enabled automatically. This ensures backward compatibility with previous versions.

### Changing Sensor Groups

1. Go to **Settings** → **Devices & Services**
2. Find the **Garmin Connect** integration
3. Click **Configure** (or the three dots menu → **Configure**)
4. Select which sensor groups you want to enable
5. Click **Submit**
6. **Reload the integration** for changes to take effect

### Per-Sensor Control

Even within enabled sensor groups, you can still disable individual sensors:

1. Go to **Settings** → **Devices & Services**
2. Find the **Garmin Connect** integration
3. Click on the device
4. Find the sensor you want to disable
5. Click on it and toggle **Enable entity** off

## Backward Compatibility

- **Existing installations**: If you upgrade from a previous version, all default sensor groups will be automatically enabled, maintaining your current setup
- **Configuration-less**: If you never configure sensor groups, all default groups remain enabled
- **Individual control**: The `entity_registry_enabled_default` setting on individual sensors still works within enabled groups

## Benefits

1. **Reduced Clutter**: Only see sensors relevant to your use case
2. **Performance**: Fewer entities to process in Home Assistant
3. **Organization**: Sensors are logically grouped for easier management
4. **Flexibility**: Enable/disable entire categories or individual sensors
5. **Scalability**: Easy to add new sensor categories in the future

## Examples

### Minimal Setup (Basic Activity Tracking)
Enable only:
- Activity & Steps
- Heart Rate
- Sleep

### Comprehensive Health Monitoring
Enable:
- All default groups
- Body Composition (if you have a compatible scale)
- Advanced Sensors (for detailed analysis)

### Athlete/Training Focus
Enable:
- Activity & Steps
- Heart Rate
- Stress
- Body Battery
- Intensity & Activity Time
- Fitness & Performance

## Technical Details

### Storage

Sensor group preferences are stored in the integration's options, separate from the main configuration. This allows:
- Easy reconfiguration without re-authentication
- No impact on existing authentication tokens
- Clean separation of concerns

### Implementation

- Sensor descriptions are organized into tuples by category
- A mapping dictionary links group IDs to sensor tuples
- The `get_sensors_for_groups()` function dynamically builds the sensor list
- Backward compatibility is ensured by checking for `None` options

## Future Enhancements

Potential future additions:
- Export/import sensor group configurations
- Preset configurations for different use cases
- Dynamic group enabling based on detected Garmin device capabilities
- Statistics about which groups are most commonly enabled

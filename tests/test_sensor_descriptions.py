"""Tests for Garmin Connect sensor descriptions."""

from custom_components.garmin_connect.sensor_descriptions import (
    ACTIVITY_SENSORS,
    ALL_SENSOR_DESCRIPTIONS,
    CALORIES_SENSORS,
    HEART_RATE_SENSORS,
)


def test_all_sensor_descriptions_not_empty():
    """Test that ALL_SENSOR_DESCRIPTIONS is not empty."""
    assert len(ALL_SENSOR_DESCRIPTIONS) > 0


def test_all_sensors_have_key():
    """Test that all sensors have a key."""
    for sensor in ALL_SENSOR_DESCRIPTIONS:
        assert sensor.key is not None
        assert len(sensor.key) > 0


def test_all_sensors_have_translation_key():
    """Test that all sensors have a translation_key."""
    for sensor in ALL_SENSOR_DESCRIPTIONS:
        assert sensor.translation_key is not None


def test_activity_sensors_exist():
    """Test that activity sensors are defined."""
    assert len(ACTIVITY_SENSORS) > 0


def test_calories_sensors_exist():
    """Test that calories sensors are defined."""
    assert len(CALORIES_SENSORS) > 0


def test_heart_rate_sensors_exist():
    """Test that heart rate sensors are defined."""
    assert len(HEART_RATE_SENSORS) > 0


def test_sensor_count():
    """Test that we have the expected number of sensors."""
    # Should have at least 90+ sensors
    assert len(ALL_SENSOR_DESCRIPTIONS) >= 90

"""Tests for Garmin Connect sensor platform."""

from unittest.mock import MagicMock

from custom_components.garmin_connect.sensor import (
    SENSOR_DESCRIPTIONS,
    GarminConnectSensor,
)


def test_sensor_descriptions_have_unique_keys() -> None:
    """Test that all sensor descriptions have unique keys."""
    keys = [desc.key for desc in SENSOR_DESCRIPTIONS]
    assert len(keys) == len(set(keys)), "Duplicate sensor keys found"


def test_sensor_native_value_returns_coordinator_data() -> None:
    """Test that native_value returns data from coordinator."""
    description = SENSOR_DESCRIPTIONS[0]  # totalSteps

    mock_coordinator = MagicMock()
    mock_coordinator.data = {"totalSteps": 9876}

    sensor = GarminConnectSensor(mock_coordinator, description, "test_entry_id")

    assert sensor.native_value == 9876


def test_sensor_native_value_returns_none_when_no_data() -> None:
    """Test that native_value returns None when coordinator data is None."""
    description = SENSOR_DESCRIPTIONS[0]

    mock_coordinator = MagicMock()
    mock_coordinator.data = None

    sensor = GarminConnectSensor(mock_coordinator, description, "test_entry_id")

    assert sensor.native_value is None


def test_sensor_native_value_returns_none_for_missing_key() -> None:
    """Test that native_value returns None for missing keys."""
    description = SENSOR_DESCRIPTIONS[0]  # totalSteps

    mock_coordinator = MagicMock()
    mock_coordinator.data = {}  # empty, key missing

    sensor = GarminConnectSensor(mock_coordinator, description, "test_entry_id")

    assert sensor.native_value is None


def test_sensor_unique_id_uses_entry_id_and_key() -> None:
    """Test that sensor unique ID is composed of entry_id and description key."""
    description = SENSOR_DESCRIPTIONS[0]

    mock_coordinator = MagicMock()
    sensor = GarminConnectSensor(mock_coordinator, description, "my_entry_id")

    assert sensor._attr_unique_id == f"my_entry_id_{description.key}"


def test_sensor_has_entity_name() -> None:
    """Test that sensors use has_entity_name."""
    description = SENSOR_DESCRIPTIONS[0]
    mock_coordinator = MagicMock()
    sensor = GarminConnectSensor(mock_coordinator, description, "entry_id")
    assert sensor._attr_has_entity_name is True

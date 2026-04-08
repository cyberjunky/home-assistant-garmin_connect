"""Tests for Garmin Connect sensor platform."""

from unittest.mock import MagicMock

from custom_components.garmin_connect.sensor import (
    _COORDINATOR_SENSOR_MAP,
    GarminConnectGearSensor,
    GarminConnectSensor,
    GarminConnectSensorEntityDescription,
)


def _all_descriptions() -> list[GarminConnectSensorEntityDescription]:
    """Collect all sensor descriptions from every coordinator group."""
    descs: list[GarminConnectSensorEntityDescription] = []
    for _, descriptions in _COORDINATOR_SENSOR_MAP:
        descs.extend(descriptions)
    return descs


def test_sensor_descriptions_have_unique_keys() -> None:
    """Test that all sensor descriptions have unique keys."""
    descs = _all_descriptions()
    keys = [desc.key for desc in descs]
    assert len(keys) == len(set(keys)), f"Duplicate sensor keys: {[k for k in keys if keys.count(k) > 1]}"


def test_sensor_descriptions_have_translation_keys() -> None:
    """Test that all sensor descriptions have a translation_key."""
    for desc in _all_descriptions():
        assert desc.translation_key, f"Sensor {desc.key} missing translation_key"


def test_sensor_native_value_returns_coordinator_data() -> None:
    """Test that native_value returns data from coordinator."""
    descs = _all_descriptions()
    description = descs[0]  # first sensor

    mock_coordinator = MagicMock()
    mock_coordinator.data = {description.key: 9876}

    sensor = GarminConnectSensor(mock_coordinator, description, "test_entry_id")

    assert sensor.native_value == 9876


def test_sensor_native_value_returns_none_when_no_data() -> None:
    """Test that native_value returns None when coordinator data is None."""
    description = _all_descriptions()[0]

    mock_coordinator = MagicMock()
    mock_coordinator.data = None

    sensor = GarminConnectSensor(mock_coordinator, description, "test_entry_id")

    assert sensor.native_value is None


def test_sensor_native_value_returns_none_for_missing_key() -> None:
    """Test that native_value returns None for missing keys."""
    description = _all_descriptions()[0]

    mock_coordinator = MagicMock()
    mock_coordinator.data = {}

    sensor = GarminConnectSensor(mock_coordinator, description, "test_entry_id")

    assert sensor.native_value is None


def test_sensor_unique_id_uses_entry_id_and_key() -> None:
    """Test that sensor unique ID is composed of entry_id and description key."""
    description = _all_descriptions()[0]

    mock_coordinator = MagicMock()
    sensor = GarminConnectSensor(mock_coordinator, description, "my_entry_id")

    assert sensor._attr_unique_id == f"my_entry_id_{description.key}"


def test_sensor_has_entity_name() -> None:
    """Test that sensors use has_entity_name."""
    description = _all_descriptions()[0]
    mock_coordinator = MagicMock()
    sensor = GarminConnectSensor(mock_coordinator, description, "entry_id")
    assert sensor._attr_has_entity_name is True


def test_sensor_preserve_value_retains_last_known() -> None:
    """Test that preserve_value sensors retain the last known value."""
    description = GarminConnectSensorEntityDescription(
        key="test_preserve",
        translation_key="test_preserve",
        preserve_value=True,
    )
    mock_coordinator = MagicMock()

    sensor = GarminConnectSensor(mock_coordinator, description, "entry_id")

    # First read with data
    mock_coordinator.data = {"test_preserve": 42}
    assert sensor.native_value == 42

    # Second read with None data — should preserve
    mock_coordinator.data = None
    assert sensor.native_value == 42

    # Third read with data but key missing — should preserve
    mock_coordinator.data = {}
    assert sensor.native_value == 42


def test_sensor_no_preserve_returns_none() -> None:
    """Test that non-preserve sensors return None when data is missing."""
    description = GarminConnectSensorEntityDescription(
        key="test_no_preserve",
        translation_key="test_no_preserve",
        preserve_value=False,
    )
    mock_coordinator = MagicMock()

    sensor = GarminConnectSensor(mock_coordinator, description, "entry_id")

    mock_coordinator.data = {"test_no_preserve": 10}
    assert sensor.native_value == 10

    mock_coordinator.data = None
    assert sensor.native_value is None


def test_sensor_value_fn_used_when_provided() -> None:
    """Test that value_fn overrides key-based lookup."""
    description = GarminConnectSensorEntityDescription(
        key="unused_key",
        translation_key="test_value_fn",
        value_fn=lambda data: data.get("nested", {}).get("value"),
    )
    mock_coordinator = MagicMock()
    mock_coordinator.data = {"nested": {"value": 99}}

    sensor = GarminConnectSensor(mock_coordinator, description, "entry_id")
    assert sensor.native_value == 99


def test_sensor_attributes_fn() -> None:
    """Test that extra_state_attributes uses attributes_fn."""
    description = GarminConnectSensorEntityDescription(
        key="test_attrs",
        translation_key="test_attrs",
        attributes_fn=lambda data: {"extra": data.get("detail")},
    )
    mock_coordinator = MagicMock()
    mock_coordinator.data = {"detail": "info"}

    sensor = GarminConnectSensor(mock_coordinator, description, "entry_id")
    assert sensor.extra_state_attributes == {"extra": "info"}


def test_sensor_attributes_fn_none_returns_empty() -> None:
    """Test that extra_state_attributes is empty when no attributes_fn."""
    description = GarminConnectSensorEntityDescription(
        key="test_no_attrs",
        translation_key="test_no_attrs",
    )
    mock_coordinator = MagicMock()
    mock_coordinator.data = {"test_no_attrs": 5}

    sensor = GarminConnectSensor(mock_coordinator, description, "entry_id")
    assert sensor.extra_state_attributes == {}


def test_gear_sensor_native_value() -> None:
    """Test gear sensor returns distance for matching UUID."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = {
        "gearStats": [
            {"uuid": "abc-123", "totalDistance": 1234.5, "displayName": "My Shoes"},
        ]
    }

    sensor = GarminConnectGearSensor(
        mock_coordinator, gear_uuid="abc-123", gear_name="My Shoes", entry_id="eid"
    )
    assert sensor.native_value == 1234.5


def test_gear_sensor_returns_none_when_uuid_not_found() -> None:
    """Test gear sensor returns None when UUID doesn't match."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = {"gearStats": []}

    sensor = GarminConnectGearSensor(
        mock_coordinator, gear_uuid="missing", gear_name="Gone", entry_id="eid"
    )
    assert sensor.native_value is None


def test_gear_sensor_extra_attributes() -> None:
    """Test gear sensor exposes gear details as attributes."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = {
        "gearStats": [
            {
                "uuid": "abc-123",
                "totalDistance": 500.0,
                "totalActivities": 42,
                "dateBegin": "2024-01-01",
                "dateEnd": None,
                "gearMakeName": "Nike",
                "gearModelName": "Pegasus",
                "gearStatusName": "active",
                "customMakeModel": "Nike Pegasus 40",
                "maximumMeters": 800000,
                "defaultForActivity": ["running"],
            },
        ]
    }

    sensor = GarminConnectGearSensor(
        mock_coordinator, gear_uuid="abc-123", gear_name="Pegasus", entry_id="eid"
    )
    attrs = sensor.extra_state_attributes
    assert attrs["gear_uuid"] == "abc-123"
    assert attrs["total_activities"] == 42
    assert attrs["gear_make_name"] == "Nike"
    assert attrs["default_for_activity"] == ["running"]

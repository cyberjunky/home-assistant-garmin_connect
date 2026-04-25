"""Tests for Garmin Connect sensor platform."""

from unittest.mock import MagicMock

from custom_components.garmin_connect.sensor import (
    _COORDINATOR_SENSOR_MAP,
    ACTIVITY_TRACKING_SENSORS,
    BLOOD_PRESSURE_SENSORS,
    BODY_COMPOSITION_SENSORS,
    GEAR_SENSORS,
    GOALS_SENSORS,
    MENSTRUAL_CYCLE_SENSORS,
    TRAINING_SENSORS,
    CoordinatorType,
    GarminConnectGearSensor,
    GarminConnectSensor,
    GarminConnectSensorEntityDescription,
)

from .conftest import (
    mock_activity_data,
    mock_blood_pressure_data,
    mock_body_data,
    mock_gear_data,
    mock_goals_data,
    mock_training_data,
)


def _all_descriptions() -> list[GarminConnectSensorEntityDescription]:
    """Collect all sensor descriptions from every coordinator group."""
    descs: list[GarminConnectSensorEntityDescription] = []
    for _, descriptions in _COORDINATOR_SENSOR_MAP:
        descs.extend(descriptions)
    return descs


# ── Descriptor invariants ─────────────────────────────────────────────────────


def test_all_sensor_descriptions_have_unique_keys() -> None:
    """Every sensor description key must be unique across all coordinators."""
    descs = _all_descriptions()
    keys = [d.key for d in descs]
    assert len(keys) == len(set(keys)), (
        f"Duplicate sensor keys: {[k for k in keys if keys.count(k) > 1]}"
    )


def test_all_sensor_descriptions_have_translation_keys() -> None:
    """Every sensor description must have a translation_key or a name."""
    for desc in _all_descriptions():
        assert desc.translation_key or desc.name, (
            f"Sensor {desc.key} missing both translation_key and name"
        )


def test_coordinator_type_on_non_core_sensor_groups() -> None:
    """Non-CORE sensor groups must declare the correct coordinator_type."""
    for desc in ACTIVITY_TRACKING_SENSORS:
        assert desc.coordinator_type == CoordinatorType.ACTIVITY
    for desc in TRAINING_SENSORS:
        assert desc.coordinator_type == CoordinatorType.TRAINING
    for desc in BODY_COMPOSITION_SENSORS:
        assert desc.coordinator_type == CoordinatorType.BODY
    for desc in GOALS_SENSORS:
        assert desc.coordinator_type == CoordinatorType.GOALS
    for desc in GEAR_SENSORS:
        assert desc.coordinator_type == CoordinatorType.GEAR
    for desc in BLOOD_PRESSURE_SENSORS:
        assert desc.coordinator_type == CoordinatorType.BLOOD_PRESSURE
    for desc in MENSTRUAL_CYCLE_SENSORS:
        assert desc.coordinator_type == CoordinatorType.MENSTRUAL


def test_menstrual_sensors_disabled_by_default() -> None:
    """All menstrual sensors must be disabled by default."""
    for desc in MENSTRUAL_CYCLE_SENSORS:
        assert desc.entity_registry_enabled_default is False, (
            f"{desc.key} should be disabled by default"
        )


# ── GarminConnectSensor — basic behaviour ─────────────────────────────────────


def test_native_value_returns_data_for_key() -> None:
    """native_value must return the value for the description key."""
    descs = _all_descriptions()
    description = descs[0]

    coord = MagicMock()
    coord.data = {description.key: 9876}
    sensor = GarminConnectSensor(coord, description, "test_entry_id")

    assert sensor.native_value == 9876


def test_native_value_returns_none_when_no_data() -> None:
    """native_value must return None when coordinator.data is None."""
    description = _all_descriptions()[0]
    coord = MagicMock()
    coord.data = None
    sensor = GarminConnectSensor(coord, description, "test_entry_id")

    assert sensor.native_value is None


def test_native_value_returns_none_for_missing_key() -> None:
    """native_value returns None when the key is absent from data."""
    description = _all_descriptions()[0]
    coord = MagicMock()
    coord.data = {}
    sensor = GarminConnectSensor(coord, description, "test_entry_id")

    assert sensor.native_value is None


def test_unique_id_uses_entry_id_and_key() -> None:
    """Sensor unique_id must be '{entry_id}_{key}'."""
    description = _all_descriptions()[0]
    coord = MagicMock()
    sensor = GarminConnectSensor(coord, description, "my_entry_id")

    assert sensor._attr_unique_id == f"my_entry_id_{description.key}"


def test_has_entity_name_is_true() -> None:
    """All sensors must use has_entity_name = True."""
    description = _all_descriptions()[0]
    coord = MagicMock()
    sensor = GarminConnectSensor(coord, description, "entry_id")

    assert sensor._attr_has_entity_name is True


# ── value_fn ──────────────────────────────────────────────────────────────────


def test_value_fn_overrides_key_lookup() -> None:
    """When value_fn is set it must be used instead of key lookup."""
    desc = GarminConnectSensorEntityDescription(
        key="unused_key",
        translation_key="test_value_fn",
        value_fn=lambda data: data.get("nested", {}).get("value"),
    )
    coord = MagicMock()
    coord.data = {"nested": {"value": 99}}
    sensor = GarminConnectSensor(coord, desc, "entry_id")

    assert sensor.native_value == 99


def test_value_fn_receives_full_data_dict() -> None:
    """value_fn must receive the entire coordinator.data dict."""
    received: list = []
    desc = GarminConnectSensorEntityDescription(
        key="x",
        translation_key="x",
        value_fn=lambda d: received.append(d) or 42,
    )
    coord = MagicMock()
    coord.data = {"x": 1, "y": 2}
    sensor = GarminConnectSensor(coord, desc, "entry_id")
    _ = sensor.native_value
    assert received[0] is coord.data


# ── attributes_fn ─────────────────────────────────────────────────────────────


def test_attributes_fn_populates_extra_state_attributes() -> None:
    """attributes_fn must populate extra_state_attributes."""
    desc = GarminConnectSensorEntityDescription(
        key="test_attrs",
        translation_key="test_attrs",
        attributes_fn=lambda data: {"extra": data.get("detail")},
    )
    coord = MagicMock()
    coord.data = {"detail": "info"}
    sensor = GarminConnectSensor(coord, desc, "entry_id")

    assert sensor.extra_state_attributes == {"extra": "info"}


def test_extra_state_attributes_empty_without_attributes_fn() -> None:
    """extra_state_attributes must be empty when no attributes_fn is set."""
    desc = GarminConnectSensorEntityDescription(
        key="test_no_attrs",
        translation_key="test_no_attrs",
    )
    coord = MagicMock()
    coord.data = {"test_no_attrs": 5}
    sensor = GarminConnectSensor(coord, desc, "entry_id")

    assert sensor.extra_state_attributes == {}


def test_extra_state_attributes_empty_when_no_data() -> None:
    """extra_state_attributes must be empty when coordinator.data is None."""
    desc = GarminConnectSensorEntityDescription(
        key="x",
        translation_key="x",
        attributes_fn=lambda d: {"k": "v"},
    )
    coord = MagicMock()
    coord.data = None
    sensor = GarminConnectSensor(coord, desc, "entry_id")

    assert sensor.extra_state_attributes == {}


# ── preserve_value ────────────────────────────────────────────────────────────


def test_preserve_value_retains_last_known_value() -> None:
    """With preserve_value=True, cached value is returned when data disappears."""
    desc = GarminConnectSensorEntityDescription(
        key="test_preserve",
        translation_key="test_preserve",
        preserve_value=True,
    )
    coord = MagicMock()
    sensor = GarminConnectSensor(coord, desc, "entry_id")

    # First read with data
    coord.data = {"test_preserve": 42}
    assert sensor.native_value == 42

    # Data gone — should preserve
    coord.data = None
    assert sensor.native_value == 42

    # Data present but key missing — should preserve
    coord.data = {}
    assert sensor.native_value == 42


def test_preserve_value_false_returns_none_on_absent_data() -> None:
    """Without preserve_value, native_value must return None when data is absent."""
    desc = GarminConnectSensorEntityDescription(
        key="test_no_preserve",
        translation_key="test_no_preserve",
        preserve_value=False,
    )
    coord = MagicMock()
    sensor = GarminConnectSensor(coord, desc, "entry_id")

    coord.data = {"test_no_preserve": 10}
    assert sensor.native_value == 10

    coord.data = None
    assert sensor.native_value is None


# ── Coordinator-specific sensor correctness ───────────────────────────────────


def test_training_readiness_extracts_score() -> None:
    """trainingReadiness sensor must extract 'score' from the nested dict."""
    desc = next(d for d in TRAINING_SENSORS if d.key == "trainingReadiness")
    coord = MagicMock()
    coord.data = mock_training_data()
    sensor = GarminConnectSensor(coord, desc, "entry_id")
    assert sensor.native_value == 72


def test_hrv_status_text_sensor() -> None:
    """hrvStatusText must return the plain-text status value."""
    desc = next(d for d in TRAINING_SENSORS if d.key == "hrvStatusText")
    coord = MagicMock()
    coord.data = mock_training_data()
    sensor = GarminConnectSensor(coord, desc, "entry_id")
    assert sensor.native_value == "Balanced"


def test_endurance_score_extracts_overall() -> None:
    """enduranceScore sensor must extract overallScore."""
    desc = next(d for d in TRAINING_SENSORS if d.key == "enduranceScore")
    coord = MagicMock()
    coord.data = mock_training_data()
    sensor = GarminConnectSensor(coord, desc, "entry_id")
    assert sensor.native_value == 45


def test_weight_uses_pre_computed_kg_key() -> None:
    """Weight sensor must use 'weightKg' (ha_garmin computed), not raw grams."""
    desc = next(d for d in BODY_COMPOSITION_SENSORS if d.key == "weightKg")
    coord = MagicMock()
    coord.data = mock_body_data()
    sensor = GarminConnectSensor(coord, desc, "entry_id")
    assert sensor.native_value == 75.0


def test_badges_returns_count() -> None:
    """badges sensor must return the number of badges."""
    desc = next(d for d in GOALS_SENSORS if d.key == "badges")
    coord = MagicMock()
    coord.data = mock_goals_data()
    sensor = GarminConnectSensor(coord, desc, "entry_id")
    assert sensor.native_value == 1


def test_last_activity_returns_name_and_attributes() -> None:
    """lastActivity sensor: state = activityName, attributes include activityId."""
    desc = next(d for d in ACTIVITY_TRACKING_SENSORS if d.key == "lastActivity")
    coord = MagicMock()
    coord.data = mock_activity_data()
    sensor = GarminConnectSensor(coord, desc, "entry_id")
    assert sensor.native_value == "Morning Run"
    assert sensor.extra_state_attributes.get("activityId") == 12345


def test_last_activities_count() -> None:
    """lastActivities sensor must return the number of activities in the list."""
    desc = next(d for d in ACTIVITY_TRACKING_SENSORS if d.key == "lastActivities")
    coord = MagicMock()
    coord.data = mock_activity_data()
    sensor = GarminConnectSensor(coord, desc, "entry_id")
    assert sensor.native_value == 2


def test_bp_systolic_value_and_attributes() -> None:
    """bpSystolic: state = 120, attributes include diastolic and pulse."""
    desc = next(d for d in BLOOD_PRESSURE_SENSORS if d.key == "bpSystolic")
    coord = MagicMock()
    coord.data = mock_blood_pressure_data()
    sensor = GarminConnectSensor(coord, desc, "entry_id")
    assert sensor.native_value == 120
    attrs = sensor.extra_state_attributes
    assert attrs.get("diastolic") == 80
    assert attrs.get("pulse") == 70


def test_bp_category_returns_name() -> None:
    """bpCategoryName sensor must return the human-readable category name."""
    desc = next(d for d in BLOOD_PRESSURE_SENSORS if d.key == "bpCategoryName")
    coord = MagicMock()
    coord.data = mock_blood_pressure_data()
    sensor = GarminConnectSensor(coord, desc, "entry_id")
    assert sensor.native_value == "Normal"


def test_bp_measurement_time_returns_string() -> None:
    """bpMeasurementTime sensor must return the local measurement timestamp string."""
    desc = next(d for d in BLOOD_PRESSURE_SENSORS if d.key == "bpMeasurementTime")
    coord = MagicMock()
    coord.data = mock_blood_pressure_data()
    sensor = GarminConnectSensor(coord, desc, "entry_id")
    assert sensor.native_value == "2026-01-24T08:00:00"


def test_next_alarm_returns_first() -> None:
    """nextAlarm sensor must return a timezone-aware datetime parsed from the first alarm string."""
    import datetime

    desc = next(d for d in GEAR_SENSORS if d.key == "nextAlarm")
    coord = MagicMock()
    coord.data = mock_gear_data()
    sensor = GarminConnectSensor(coord, desc, "entry_id")
    assert sensor.native_value == datetime.datetime.fromisoformat("2026-01-25T06:30:00+00:00")


def test_next_alarm_none_when_empty_list() -> None:
    """nextAlarm sensor must return None when the list is empty."""
    desc = next(d for d in GEAR_SENSORS if d.key == "nextAlarm")
    coord = MagicMock()
    coord.data = {"nextAlarm": []}
    sensor = GarminConnectSensor(coord, desc, "entry_id")
    assert sensor.native_value is None


def test_next_alarm_none_when_null() -> None:
    """nextAlarm sensor must return None when the value is null."""
    desc = next(d for d in GEAR_SENSORS if d.key == "nextAlarm")
    coord = MagicMock()
    coord.data = {"nextAlarm": None}
    sensor = GarminConnectSensor(coord, desc, "entry_id")
    assert sensor.native_value is None


def test_next_alarm_none_when_missing() -> None:
    """nextAlarm sensor must return None when the key is absent."""
    desc = next(d for d in GEAR_SENSORS if d.key == "nextAlarm")
    coord = MagicMock()
    coord.data = {}
    sensor = GarminConnectSensor(coord, desc, "entry_id")
    assert sensor.native_value is None


def test_vo2_max_extracts_value() -> None:
    """vo2MaxValue sensor must return the flattened vo2MaxValue from ha_garmin computed fields."""
    desc = next(d for d in TRAINING_SENSORS if d.key == "vo2Max")
    coord = MagicMock()
    coord.data = mock_training_data()
    sensor = GarminConnectSensor(coord, desc, "entry_id")
    assert sensor.native_value == 37.0


def test_vo2_max_none_when_missing() -> None:
    """vo2Max sensor must return None when vo2MaxValue is absent."""
    desc = next(d for d in TRAINING_SENSORS if d.key == "vo2Max")
    coord = MagicMock()
    coord.data = {}
    sensor = GarminConnectSensor(coord, desc, "entry_id")
    assert sensor.native_value is None


# ── GarminConnectGearSensor ───────────────────────────────────────────────────


def test_gear_sensor_returns_total_distance() -> None:
    """Gear sensor native_value must be totalDistance for its UUID."""
    coord = MagicMock()
    coord.data = mock_gear_data()
    sensor = GarminConnectGearSensor(
        coord, gear_uuid="gear-uuid-1", gear_name="Running Shoes", entry_id="eid"
    )
    assert sensor.native_value == 500000.0


def test_gear_sensor_none_for_unknown_uuid() -> None:
    """Gear sensor must return None when UUID is not in gearStats."""
    coord = MagicMock()
    coord.data = {"gearStats": []}
    sensor = GarminConnectGearSensor(coord, gear_uuid="missing", gear_name="Gone", entry_id="eid")
    assert sensor.native_value is None


def test_gear_sensor_none_when_no_data() -> None:
    """Gear sensor must return None when coordinator.data is None."""
    coord = MagicMock()
    coord.data = None
    sensor = GarminConnectGearSensor(
        coord, gear_uuid="gear-uuid-1", gear_name="Running Shoes", entry_id="eid"
    )
    assert sensor.native_value is None


def test_gear_sensor_attributes() -> None:
    """Gear sensor attributes must expose gear_uuid, total_activities and make/model."""
    coord = MagicMock()
    coord.data = mock_gear_data()
    sensor = GarminConnectGearSensor(
        coord, gear_uuid="gear-uuid-1", gear_name="Pegasus", entry_id="eid"
    )
    attrs = sensor.extra_state_attributes
    assert attrs["gear_uuid"] == "gear-uuid-1"
    assert attrs["total_activities"] == 50
    assert attrs["gear_make_name"] == "Nike"
    assert attrs["default_for_activity"] == ["running"]


def test_gear_sensor_name_property() -> None:
    """Gear sensor .name must return the gear_name."""
    coord = MagicMock()
    coord.data = {}
    sensor = GarminConnectGearSensor(
        coord, gear_uuid="uuid", gear_name="Trail Shoes", entry_id="eid"
    )
    assert sensor.name == "Trail Shoes"


def test_gear_sensor_unique_id() -> None:
    """Gear sensor unique_id must be '{entry_id}_gear_{gear_uuid}'."""
    coord = MagicMock()
    coord.data = {}
    sensor = GarminConnectGearSensor(
        coord, gear_uuid="abc-123", gear_name="My Trail Shoes", entry_id="my_entry"
    )
    assert sensor._attr_unique_id == "my_entry_gear_abc-123"


def test_gear_sensor_unique_id_unnamed_gear_no_collision() -> None:
    """Two unnamed gear items with different UUIDs must have distinct unique_ids."""
    coord = MagicMock()
    coord.data = {}
    sensor_a = GarminConnectGearSensor(
        coord, gear_uuid="abc-123", gear_name=None, entry_id="my_entry"
    )
    sensor_b = GarminConnectGearSensor(
        coord, gear_uuid="def-456", gear_name=None, entry_id="my_entry"
    )
    assert sensor_a._attr_unique_id == "my_entry_gear_abc-123"
    assert sensor_b._attr_unique_id == "my_entry_gear_def-456"
    assert sensor_a._attr_unique_id != sensor_b._attr_unique_id

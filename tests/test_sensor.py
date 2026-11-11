"""Tests for the Garmin Connect sensor platform.

Entity behaviour is tested through Home Assistant: the integration is set up
with ha-garmin mocked, and states, attributes and the entity registry are
read back from ``hass``. Per-test data is passed by parametrizing the
``garmin_data`` fixture, or pushed after setup with ``_push``, which refreshes
the coordinator the way a poll does. Only module-level metadata (descriptions,
strings.json, icons.json) is checked directly.
"""

import asyncio
import datetime
import json
from datetime import date
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from freezegun.api import FrozenDateTimeFactory
from ha_garmin import GarminConnectError
from homeassistant.components.recorder.db_schema import StateAttributes
from homeassistant.components.sensor import (
    ATTR_LAST_RESET,
    ATTR_OPTIONS,
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    EVENT_STATE_CHANGED,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import Event, HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant.common import (
    MockConfigEntry,
    mock_restore_cache,
    mock_restore_cache_with_extra_data,
)

from custom_components.garmin_connect.const import DOMAIN
from custom_components.garmin_connect.coordinator import (
    LATEST_HEART_RATE_CONTEXT,
    LIFETIME_CONTEXT,
    YESTERDAY_CONTEXT,
)
from custom_components.garmin_connect.sensor import (
    _COORDINATOR_SENSOR_MAP,
    ACTIVITY_TRACKING_SENSORS,
    BLOOD_PRESSURE_SENSORS,
    BODY_COMPOSITION_SENSORS,
    GEAR_SENSORS,
    GOALS_SENSORS,
    MENSTRUAL_CYCLE_SENSORS,
    NUTRITION_SENSORS,
    TRAINING_SENSORS,
    CoordinatorType,
    GarminConnectSensorEntityDescription,
)

from .conftest import (
    mock_activity_data,
    mock_body_data,
    mock_goals_data,
    mock_menstrual_data,
    mock_nutrition_data,
    mock_training_data,
)

ENTRY_ID = "test_entry_id"

# Attributes Home Assistant adds itself; everything else came from the integration.
_HA_ATTRIBUTES = frozenset(
    {
        ATTR_DEVICE_CLASS,
        ATTR_FRIENDLY_NAME,
        ATTR_ICON,
        ATTR_LAST_RESET,
        ATTR_OPTIONS,
        ATTR_STATE_CLASS,
        ATTR_UNIT_OF_MEASUREMENT,
    }
)

enable_all = pytest.mark.usefixtures("entity_registry_enabled_by_default")


def _all_descriptions() -> list[GarminConnectSensorEntityDescription]:
    """Collect all sensor descriptions from every coordinator group."""
    descs: list[GarminConnectSensorEntityDescription] = []
    for _, descriptions in _COORDINATOR_SENSOR_MAP:
        descs.extend(descriptions)
    return descs


def _desc(key: str) -> GarminConnectSensorEntityDescription:
    return next(d for d in _all_descriptions() if d.key == key)


# ── Fixtures and helpers ──────────────────────────────────────────────────────


@pytest.fixture
def garmin_data(request: pytest.FixtureRequest, mock_client: MagicMock) -> None:
    """Replace what ``fetch_<coordinator>_data`` returns, before setup.

    Parametrize with ``indirect=True`` and a ``{coordinator: data}`` mapping;
    coordinators left out keep the conftest sample data.
    """
    for coordinator, data in getattr(request, "param", {}).items():
        getattr(mock_client, f"fetch_{coordinator}_data").return_value = data


@pytest.fixture
async def entry(garmin_data: None, init_integration: MockConfigEntry) -> MockConfigEntry:
    """The integration set up through Home Assistant with ``garmin_data`` applied."""
    del garmin_data  # requested only so it runs before init_integration
    return init_integration


@pytest.fixture
def prepared_entry(
    hass: HomeAssistant,
    garmin_data: None,
    ha_environment: None,
    mock_config_entry: MockConfigEntry,
    mock_auth: MagicMock,
    mock_client: MagicMock,
) -> MockConfigEntry:
    """A config entry added but not set up, for tests that seed the registry or restore cache."""
    del garmin_data, ha_environment  # requested for their side effects only
    mock_client.today.return_value = date(2026, 1, 15)
    mock_client.get_daily_summary = AsyncMock(return_value={})
    mock_config_entry.add_to_hass(hass)
    return mock_config_entry


async def _setup(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)


async def _push(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    coordinator: str,
    data: dict[str, Any] | None,
) -> None:
    """Have the next poll of one coordinator return ``data`` and run that poll."""
    getattr(mock_client, f"fetch_{coordinator}_data").return_value = data
    await getattr(config_entry.runtime_data, coordinator).async_refresh()
    await hass.async_block_till_done()


def _uid(suffix: str) -> str:
    return f"{ENTRY_ID}_{suffix}"


def _entity_id(hass: HomeAssistant, suffix: str) -> str | None:
    return er.async_get(hass).async_get_entity_id(Platform.SENSOR, DOMAIN, _uid(suffix))


def _state(hass: HomeAssistant, suffix: str) -> State:
    """State of the sensor whose unique_id is ``{entry_id}_{suffix}``."""
    entity_id = _entity_id(hass, suffix)
    assert entity_id is not None, f"no entity for {suffix}"
    state = hass.states.get(entity_id)
    assert state is not None, f"no state for {entity_id}"
    return state


def _extra(state: State) -> dict[str, Any]:
    """The integration's own attributes, without the ones Home Assistant adds."""
    return {k: v for k, v in state.attributes.items() if k not in _HA_ATTRIBUTES}


def _register(
    hass: HomeAssistant, config_entry: MockConfigEntry, suffix: str, object_id: str
) -> er.RegistryEntry:
    """Put a sensor in the registry as if an earlier run had created it."""
    return er.async_get(hass).async_get_or_create(
        Platform.SENSOR,
        DOMAIN,
        _uid(suffix),
        config_entry=config_entry,
        suggested_object_id=object_id,
    )


def _registered(hass: HomeAssistant, prefix: str) -> set[str]:
    """Unique-id suffixes of the entry's sensors starting with ``prefix``."""
    return {
        e.unique_id.removeprefix(f"{ENTRY_ID}_")
        for e in er.async_entries_for_config_entry(er.async_get(hass), ENTRY_ID)
        if e.domain == Platform.SENSOR and e.unique_id.startswith(_uid(prefix))
    }


def _recorded_attributes(state: State) -> bytes:
    """Serialize a live state's attributes through the recorder's own encoder."""
    event = Event(
        EVENT_STATE_CHANGED,
        {"entity_id": state.entity_id, "old_state": None, "new_state": state},
    )
    return StateAttributes.shared_attrs_bytes_from_event(event, None)


def _training(ptw: list[dict[str, Any]] | None) -> dict[str, Any]:
    return {**mock_training_data(), "powerToWeight": ptw}


def _gear(*stats: dict[str, Any]) -> dict[str, Any]:
    return {"gearStats": list(stats)}


def _day_summary(**changes: Any) -> dict[str, Any]:
    summary = dict(mock_menstrual_data()["menstrualData"]["daySummary"])
    summary.update(changes)
    return {k: v for k, v in summary.items() if v is not None}


# ── Descriptor invariants (module metadata, no entities) ──────────────────────


def test_all_sensor_descriptions_have_unique_keys() -> None:
    """Every sensor description key must be unique across all coordinators."""
    keys = [d.key for d in _all_descriptions()]
    assert len(keys) == len(set(keys)), (
        f"Duplicate sensor keys: {[k for k in keys if keys.count(k) > 1]}"
    )


def test_all_sensor_descriptions_have_translation_keys() -> None:
    """Every sensor description must have a translation_key or a name."""
    for desc in _all_descriptions():
        assert desc.translation_key or desc.name, (
            f"Sensor {desc.key} missing both translation_key and name"
        )


def test_no_sensor_uses_total_without_last_reset() -> None:
    """TOTAL is only used by daily totals, which supply last_reset.

    Without last_reset, Home Assistant subtracts each daily reset from the
    long-term sum, so daily statistics of Garmin's daily counters go negative.
    """
    for desc in _all_descriptions():
        is_total = desc.state_class == SensorStateClass.TOTAL
        assert is_total == desc.daily_total, (
            f"{desc.key}: TOTAL needs daily_total=True (for last_reset), and "
            "daily_total needs TOTAL; use TOTAL_INCREASING for counters that "
            "never go down or MEASUREMENT for values that do not accumulate"
        )


def test_coordinator_type_on_sensor_groups() -> None:
    """Each sensor group declares the coordinator it is fed by."""
    for coord_type, descriptions in _COORDINATOR_SENSOR_MAP:
        for desc in descriptions:
            assert desc.coordinator_type == coord_type, desc.key
    for group, coord_type in (
        (ACTIVITY_TRACKING_SENSORS, CoordinatorType.ACTIVITY),
        (TRAINING_SENSORS, CoordinatorType.TRAINING),
        (BODY_COMPOSITION_SENSORS, CoordinatorType.BODY),
        (GOALS_SENSORS, CoordinatorType.GOALS),
        (GEAR_SENSORS, CoordinatorType.GEAR),
        (BLOOD_PRESSURE_SENSORS, CoordinatorType.BLOOD_PRESSURE),
        (MENSTRUAL_CYCLE_SENSORS, CoordinatorType.MENSTRUAL),
        (NUTRITION_SENSORS, CoordinatorType.NUTRITION),
    ):
        assert all(d.coordinator_type == coord_type for d in group)


def test_enum_options_have_state_translations() -> None:
    """Every ENUM option has a translated state in strings.json."""
    strings = json.loads(
        (Path(__file__).parent.parent / "custom_components/garmin_connect/strings.json").read_text()
    )["entity"]["sensor"]
    for desc in _all_descriptions():
        if desc.device_class != SensorDeviceClass.ENUM:
            continue
        states = strings[desc.translation_key].get("state", {})
        assert set(desc.options) == set(states), desc.key


def test_every_sensor_has_an_icon() -> None:
    """Every sensor translation key has an icon in icons.json."""
    icons = json.loads(
        (Path(__file__).parent.parent / "custom_components/garmin_connect/icons.json").read_text()
    )["entity"]["sensor"]
    missing = {d.translation_key for d in _all_descriptions() if d.translation_key not in icons}
    assert not missing


def test_route_sensor_is_translated() -> None:
    desc = _desc("lastActivityRoute")
    assert desc.translation_key == "last_activity_route"
    assert not isinstance(desc.name, str)


@pytest.mark.parametrize(
    ("key", "device_class", "state_class"),
    [
        ("lactateThresholdSpeed", SensorDeviceClass.SPEED, SensorStateClass.MEASUREMENT),
        ("totalActivityTimeGainMinutes", SensorDeviceClass.DURATION, None),
        ("trainingReadiness", None, SensorStateClass.MEASUREMENT),
        ("morningTrainingReadiness", None, SensorStateClass.MEASUREMENT),
        ("lactateThresholdHeartRate", None, SensorStateClass.MEASUREMENT),
    ],
)
def test_sensor_classes(
    key: str, device_class: SensorDeviceClass | None, state_class: SensorStateClass | None
) -> None:
    """Device and state classes let HA convert units and keep statistics."""
    desc = _desc(key)
    if device_class is not None:
        assert desc.device_class == device_class
    if state_class is not None:
        assert desc.state_class == state_class


@pytest.mark.parametrize(
    "group", [MENSTRUAL_CYCLE_SENSORS, NUTRITION_SENSORS], ids=["menstrual", "nutrition"]
)
def test_privacy_and_paid_sensor_groups_disabled_by_default(
    group: tuple[GarminConnectSensorEntityDescription, ...],
) -> None:
    """Menstrual (privacy) and nutrition (Connect+) sensors are opt-in."""
    for desc in group:
        assert desc.entity_registry_enabled_default is False, (
            f"{desc.key} should be disabled by default"
        )


# ── Registry and naming ───────────────────────────────────────────────────────


async def test_unique_id_and_entity_name(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Sensors register as '{entry_id}_{key}' with has_entity_name on the service device."""
    reg_entry = er.async_get(hass).async_get("sensor.garmin_connect_steps")
    assert reg_entry is not None
    assert reg_entry.unique_id == "test_entry_id_totalSteps"
    assert reg_entry.has_entity_name is True
    assert reg_entry.config_entry_id == ENTRY_ID
    assert hass.states.get("sensor.garmin_connect_steps").state == "10000"


async def test_opt_in_sensors_are_disabled_in_the_registry(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Every description marked disabled-by-default lands disabled in the registry."""
    registry = er.async_get(hass)
    for desc in _all_descriptions():
        reg_entry = registry.async_get(_entity_id(hass, desc.key))
        if desc.entity_registry_enabled_default:
            assert reg_entry.disabled_by is None, desc.key
        else:
            assert reg_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION, desc.key
            assert hass.states.get(reg_entry.entity_id) is None


# ── Opt-in data (coordinator contexts) ────────────────────────────────────────


async def test_yesterday_summary_not_fetched_while_sensors_disabled(
    hass: HomeAssistant, entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Yesterday's summary costs an API call, so it is skipped while no sensor wants it."""
    on_demand = [d for d in _all_descriptions() if d.coordinator_context == YESTERDAY_CONTEXT]
    assert len(on_demand) == 12
    assert all(d.entity_registry_enabled_default is False for d in on_demand)

    assert YESTERDAY_CONTEXT not in set(entry.runtime_data.core.async_contexts())
    mock_client.get_daily_summary.assert_not_awaited()
    # Yesterday steps/distance come free with today's data.
    assert _state(hass, "yesterdaySteps").state == "9500"


@enable_all
async def test_yesterday_summary_fetched_once_a_sensor_is_enabled(
    hass: HomeAssistant, entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    assert YESTERDAY_CONTEXT in set(entry.runtime_data.core.async_contexts())
    mock_client.get_daily_summary.assert_awaited_with(date(2026, 1, 14))


@enable_all
async def test_latest_heart_rate_sensor(
    hass: HomeAssistant, entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Opt-in; value and measurement_time come from ha-garmin's latest sample."""
    desc = _desc("latestHeartRate")
    assert desc.entity_registry_enabled_default is False
    assert desc.coordinator_context == LATEST_HEART_RATE_CONTEXT
    assert LATEST_HEART_RATE_CONTEXT in set(entry.runtime_data.core.async_contexts())
    mock_client.fetch_core_data.assert_awaited_with(latest_heart_rate=True)

    measured = datetime.datetime(2026, 10, 30, 5, 48, tzinfo=datetime.UTC)
    await _push(
        hass, entry, mock_client, "core", {"latestHeartRate": 56, "latestHeartRateTime": measured}
    )
    state = _state(hass, "latestHeartRate")
    assert state.state == "56"
    assert _extra(state) == {"measurement_time": measured}

    await _push(
        hass, entry, mock_client, "core", {"latestHeartRate": None, "latestHeartRateTime": None}
    )
    state = _state(hass, "latestHeartRate")
    assert state.state == STATE_UNKNOWN
    assert _extra(state) == {}


@enable_all
async def test_lifetime_sensors_opt_in_and_unavailable_while_hidden(
    hass: HomeAssistant, entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Lifetime totals cost a request and need a profile setting: opt-in, explained when hidden."""
    lifetime = [d for d in GOALS_SENSORS if d.key.startswith("lifetime")]
    assert len(lifetime) == 4
    assert all(d.coordinator_context == LIFETIME_CONTEXT for d in lifetime)
    assert all(d.entity_registry_enabled_default is False for d in lifetime)
    mock_client.fetch_goals_data.assert_awaited_with(lifetime_totals=True)

    assert {d.key: _state(hass, d.key).state for d in lifetime} == {
        "lifetimeSteps": "10428222",
        "lifetimeDistance": "8123.456",  # m -> km
        "lifetimeCalories": "4567890",
        "lifetimeActiveDays": "2350",
    }

    await _push(
        hass,
        entry,
        mock_client,
        "goals",
        {**mock_goals_data(), "lifetimeTotals": {}, "lifetimeTotalsHidden": True},
    )
    assert _state(hass, "lifetimeSteps").state == STATE_UNAVAILABLE


@enable_all
@pytest.mark.parametrize("garmin_data", [{"goals": {"lifetimeTotals": {}}}], indirect=True)
async def test_lifetime_totals_missing_is_unknown(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    assert _state(hass, "lifetimeSteps").state == STATE_UNKNOWN


# ── Basic value / attribute handling ──────────────────────────────────────────


@pytest.mark.parametrize("garmin_data", [{"core": {"dailyStepGoal": 9876}}], indirect=True)
async def test_state_is_the_value_for_the_description_key(
    hass: HomeAssistant, entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Without a value_fn the state is the coordinator value under the key."""
    assert _state(hass, "dailyStepGoal").state == "9876"
    # Without an attributes_fn there are no extra attributes.
    assert _extra(_state(hass, "dailyStepGoal")) == {}

    await _push(hass, entry, mock_client, "core", {"other": 1})
    assert _state(hass, "dailyStepGoal").state == STATE_UNKNOWN

    await _push(hass, entry, mock_client, "core", {})
    assert _state(hass, "dailyStepGoal").state == STATE_UNKNOWN


async def test_preserved_value_survives_missing_data(
    hass: HomeAssistant, entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """With preserve_value the last value stays when Garmin stops reporting it."""
    assert _desc("weightKg").preserve_value
    assert _state(hass, "weightKg").state == "75.0"

    await _push(hass, entry, mock_client, "body", {})
    assert _state(hass, "weightKg").state == "75.0"

    await _push(hass, entry, mock_client, "body", {"bmi": 24.0})
    assert _state(hass, "weightKg").state == "75.0"

    await _push(hass, entry, mock_client, "body", None)
    assert _state(hass, "weightKg").state == "75.0"


async def test_non_preserved_value_goes_unknown(
    hass: HomeAssistant, entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Without preserve_value a missing value is unknown and no data is unavailable."""
    assert not _desc("fitnessAge").preserve_value
    assert _state(hass, "fitnessAge").state == "30"

    await _push(hass, entry, mock_client, "body", {})
    assert _state(hass, "fitnessAge").state == STATE_UNKNOWN

    await _push(hass, entry, mock_client, "body", None)
    assert _state(hass, "fitnessAge").state == STATE_UNAVAILABLE


async def test_preserved_sensor_keeps_attributes_while_data_is_empty(
    hass: HomeAssistant, entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """A preserved sensor keeps its attributes along with its value when Garmin has no data."""
    assert _desc("lactateThresholdSpeed").preserve_value
    state = _state(hass, "lactateThresholdSpeed")
    assert state.state == "11.52"  # 3.2 m/s in km/h
    assert _extra(state) == {"speed": 3.2, "hearRate": 162}

    await _push(hass, entry, mock_client, "training", {})
    state = _state(hass, "lactateThresholdSpeed")
    assert state.state == "11.52"
    assert _extra(state) == {"speed": 3.2, "hearRate": 162}


@pytest.mark.parametrize("garmin_data", [{"training": {"trainingStatus": {"x": 1}}}], indirect=True)
async def test_non_preserved_sensor_drops_attributes_while_data_is_empty(
    hass: HomeAssistant, entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Sensors without preserve_value show no stale attributes."""
    assert _extra(_state(hass, "trainingStatus")) == {"x": 1}
    await _push(hass, entry, mock_client, "training", {})
    assert _extra(_state(hass, "trainingStatus")) == {}


async def test_available_waits_for_first_fetch(
    hass: HomeAssistant, prepared_entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Before the first fetch only sensors with a restored value are available."""
    release = asyncio.Event()

    async def _slow_body_fetch() -> dict[str, Any]:
        await release.wait()
        return mock_body_data()

    mock_client.fetch_body_data.side_effect = _slow_body_fetch
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State("sensor.garmin_connect_weight", "81.5"),
                {"native_value": 81.5, "native_unit_of_measurement": "kg"},
            )
        ],
    )
    assert await hass.config_entries.async_setup(prepared_entry.entry_id)
    await hass.async_block_till_done()

    # Preserved with a restored value / preserved without one / not preserved.
    assert _state(hass, "weightKg").state == "81.5"
    assert _state(hass, "bmi").state == STATE_UNAVAILABLE
    assert _state(hass, "fitnessAge").state == STATE_UNAVAILABLE

    release.set()
    await hass.async_block_till_done(wait_background_tasks=True)
    assert _state(hass, "weightKg").state == "75.0"
    assert _state(hass, "fitnessAge").state == "30"

    mock_client.fetch_body_data.side_effect = GarminConnectError("down")
    await prepared_entry.runtime_data.body.async_refresh()
    await hass.async_block_till_done()
    assert _state(hass, "weightKg").state == STATE_UNAVAILABLE
    assert _state(hass, "fitnessAge").state == STATE_UNAVAILABLE


# ── Value restore ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize("garmin_data", [{"body": {}}], indirect=True)
async def test_preserve_value_restored_from_last_state(
    hass: HomeAssistant, prepared_entry: MockConfigEntry
) -> None:
    """After a restart a preserved sensor reports its stored value until data arrives."""
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State("sensor.garmin_connect_weight", "81.5"),
                {"native_value": 81.5, "native_unit_of_measurement": "kg"},
            )
        ],
    )
    await _setup(hass, prepared_entry)
    assert _state(hass, "weightKg").state == "81.5"


@pytest.mark.parametrize("garmin_data", [{"core": {}}], indirect=True)
async def test_non_preserved_sensor_does_not_restore(
    hass: HomeAssistant, prepared_entry: MockConfigEntry
) -> None:
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State("sensor.garmin_connect_daily_step_goal", "9999"),
                {"native_value": 9999, "native_unit_of_measurement": None},
            )
        ],
    )
    await _setup(hass, prepared_entry)
    assert _state(hass, "dailyStepGoal").state == STATE_UNKNOWN


@pytest.mark.parametrize("garmin_data", [{"body": {}}], indirect=True)
async def test_preserved_sensor_without_stored_sensor_data_stays_unknown(
    hass: HomeAssistant, prepared_entry: MockConfigEntry
) -> None:
    """A restored state without sensor extra data restores nothing."""
    mock_restore_cache(hass, [State("sensor.garmin_connect_weight", "81.5")])
    await _setup(hass, prepared_entry)
    assert _state(hass, "weightKg").state == STATE_UNKNOWN


# ── Daily totals ──────────────────────────────────────────────────────────────


@enable_all
async def test_daily_total_resets_at_local_midnight(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Daily totals report local midnight as last_reset; other sensors none."""
    daily = _state(hass, "nutritionConsumedCalories")
    assert daily.attributes[ATTR_STATE_CLASS] == SensorStateClass.TOTAL
    assert daily.attributes[ATTR_LAST_RESET] == dt_util.start_of_local_day().isoformat()
    assert ATTR_LAST_RESET not in _state(hass, "nutritionCalorieGoal").attributes


# ── Nutrition ─────────────────────────────────────────────────────────────────


@enable_all
async def test_nutrition_sensor_values(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Nutrition sensors resolve values by key; consumed calories carry the meals."""
    data = mock_nutrition_data()
    for desc in NUTRITION_SENSORS:
        value = data[desc.key]
        expected = value.isoformat() if isinstance(value, datetime.datetime) else str(value)
        assert _state(hass, desc.key).state == expected, desc.key
    assert len(_state(hass, "nutritionConsumedCalories").attributes["meals"]) == 3


@enable_all
@pytest.mark.parametrize("garmin_data", [{"nutrition": {}}], indirect=True)
async def test_nutrition_sensors_unknown_when_feature_unavailable(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Empty coordinator data (no Connect+) -> sensors report unknown, no attributes."""
    for desc in NUTRITION_SENSORS:
        state = _state(hass, desc.key)
        assert state.state == STATE_UNKNOWN, desc.key
        assert _extra(state) == {}, desc.key


# ── Core: health and sleep ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "garmin_data",
    [{"core": {"avgSkinTempDeviationC": 0.2, "skinTempCalibrationDays": 19}}],
    indirect=True,
)
async def test_skin_temp_change_sensor(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Skin temperature change is a delta, with calibration days attached."""
    state = _state(hass, "avgSkinTempDeviationC")
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TEMPERATURE_DELTA
    assert state.state == "0.2"
    assert _extra(state) == {"calibration_days": 19}


@pytest.mark.parametrize(
    "garmin_data",
    [
        {
            "core": {
                "sleepScore": 85,
                "sleepScores": {
                    "overall": {"value": 85, "qualifierKey": "GOOD"},
                    "totalDuration": {"qualifierKey": "EXCELLENT"},
                    "stress": {"qualifierKey": "FAIR", "optimalStart": 0.0, "optimalEnd": 15.0},
                    "remPercentage": {"value": 20, "qualifierKey": "FAIR"},
                },
                "sleepScoreFeedback": "POSITIVE_LONG_AND_DEEP",
                "sleepScoreInsight": "NONE",
                "sleepScorePersonalizedInsight": "RHYTHM_POS_GOOD_SLEEP",
            }
        }
    ],
    indirect=True,
)
async def test_sleep_score_attributes(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Sleep score carries Garmin's per-component qualifiers and feedback keys."""
    state = _state(hass, "sleepScore")
    assert state.state == "85"
    attributes = state.attributes
    assert attributes["qualifier"] == "good"
    assert attributes["duration_qualifier"] == "excellent"
    assert attributes["stress_qualifier"] == "fair"
    assert attributes["rem_qualifier"] == "fair"
    assert attributes["rem_percentage"] == 20
    assert attributes["deep_qualifier"] is None
    assert "deep_percentage" not in attributes
    assert attributes["feedback"] == "POSITIVE_LONG_AND_DEEP"
    assert attributes["personalized_insight"] == "RHYTHM_POS_GOOD_SLEEP"


@pytest.mark.parametrize(
    "garmin_data", [{"core": {"sleepScore": None, "sleepScores": None}}], indirect=True
)
async def test_sleep_score_attributes_empty_without_scores(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """No sleep yet (midnight) -> no attributes rather than a dict of Nones."""
    assert _extra(_state(hass, "sleepScore")) == {}


async def test_avg_sleep_stress_sensor(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Average sleep stress exposes Garmin's qualifier and optimal range."""
    state = _state(hass, "avgSleepStress")
    assert state.state == "21.0"
    assert _extra(state) == {"qualifier": "fair", "optimal_start": 0.0, "optimal_end": 15.0}


_SLEEP_STRESS = [
    {"time": datetime.datetime(2026, 4, 11, 22, 0, tzinfo=datetime.UTC), "value": 18.0},
    {"time": datetime.datetime(2026, 4, 11, 22, 3, tzinfo=datetime.UTC), "value": 22.0},
]


@pytest.mark.parametrize(
    "garmin_data", [{"core": {"avgSleepStress": 21.0, "sleepStress": _SLEEP_STRESS}}], indirect=True
)
async def test_avg_sleep_stress_samples(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """The overnight stress samples ride along as an attribute, live-only."""
    state = _state(hass, "avgSleepStress")
    assert _extra(state) == {"sleep_stress": _SLEEP_STRESS}
    assert "sleep_stress" not in json.loads(_recorded_attributes(state))


async def test_sleep_night_sensors(
    hass: HomeAssistant, entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Awakenings, restless moments, sleep heart rate and overnight body battery change."""
    expected = {
        "awakeCount": "2",
        "restlessMomentsCount": "50",
        "avgSleepHeartRate": "58.0",
        "sleepBodyBatteryChange": "48",
    }
    assert {key: _state(hass, key).state for key in expected} == expected
    # All of them keep last night's value through the day.
    await _push(hass, entry, mock_client, "core", {"totalSteps": 1})
    assert {key: _state(hass, key).state for key in expected} == expected


# ── ENUM sensors ──────────────────────────────────────────────────────────────


async def test_hrv_status_text_sensor(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """hrvStatusText is an ENUM whose state is the normalized status."""
    state = _state(hass, "hrvStatusText")
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.ENUM
    assert state.state == "balanced"


@pytest.mark.parametrize(
    ("garmin_data", "key", "expected"),
    [
        ({"training": {"trainingStatusPhrase": "No Status"}}, "trainingStatus", "no_status"),
        ({"training": {"trainingStatusPhrase": "Overreaching"}}, "trainingStatus", "overreaching"),
        (
            {"core": {"stressQualifierText": "Very_stressful"}},
            "stressQualifierText",
            "very_stressful",
        ),
        ({"core": {"stressQualifierText": "Unknown"}}, "stressQualifierText", STATE_UNKNOWN),
        (
            {"core": {"stressQualifierText": "Stressful_awake"}},
            "stressQualifierText",
            "stressful",
        ),
        (
            {"core": {"stressQualifierText": "Very_stressful_awake"}},
            "stressQualifierText",
            "very_stressful",
        ),
        ({"training": {"hrvStatusText": "Unbalanced"}}, "hrvStatusText", "unbalanced"),
        ({"training": {"hrvStatusText": None}}, "hrvStatusText", STATE_UNKNOWN),
    ],
    indirect=["garmin_data"],
)
async def test_enum_sensors_normalize_garmin_labels(
    hass: HomeAssistant, entry: MockConfigEntry, key: str, expected: str
) -> None:
    """Garmin labels map onto the ENUM options; no-value labels become unknown."""
    state = _state(hass, key)
    assert state.state == expected
    assert expected == STATE_UNKNOWN or expected in state.attributes[ATTR_OPTIONS]


@pytest.mark.parametrize("garmin_data", [{"training": {}}], indirect=True)
async def test_enum_restore_normalizes_state_saved_before_enum(
    hass: HomeAssistant, prepared_entry: MockConfigEntry
) -> None:
    """Upgrading from a text sensor: the saved "Balanced" restores as an option (#676)."""
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State("sensor.garmin_connect_hrv_status", "Balanced"),
                {"native_value": "Balanced", "native_unit_of_measurement": None},
            )
        ],
    )
    await _setup(hass, prepared_entry)
    assert _state(hass, "hrvStatusText").state == "balanced"


@pytest.mark.parametrize("garmin_data", [{"training": {}}], indirect=True)
async def test_enum_restore_drops_state_outside_options(
    hass: HomeAssistant, prepared_entry: MockConfigEntry
) -> None:
    """A saved state that matches no option is not restored at all."""
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State("sensor.garmin_connect_hrv_status", "Something Else"),
                {"native_value": "Something Else", "native_unit_of_measurement": None},
            )
        ],
    )
    await _setup(hass, prepared_entry)
    assert _state(hass, "hrvStatusText").state == STATE_UNKNOWN


async def test_enum_sensor_unknown_label_is_logged_once(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A label Garmin adds later is reported once and shown as unknown."""
    for _ in range(2):
        await _push(
            hass, entry, mock_client, "training", {"trainingStatusPhrase": "Brand New Status"}
        )
        assert _state(hass, "trainingStatus").state == STATE_UNKNOWN
    assert caplog.text.count("Brand New Status") == 1


# ── Training ──────────────────────────────────────────────────────────────────


async def test_training_sensors_from_nested_data(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Value functions extract scores from ha-garmin's nested training data."""
    assert _state(hass, "trainingReadiness").state == "72"
    assert _state(hass, "enduranceScore").state == "45"
    assert _state(hass, "vo2Max").state == "37.0"


async def test_training_vo2_cycling_and_acclimation(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Cycling VO2 max and heat/altitude acclimation come from fetch_training_data."""
    assert _state(hass, "vo2MaxCycling").state == "41.0"
    heat = _state(hass, "heatAcclimation")
    assert heat.state == "35"
    assert _extra(heat) == {"trend": "ACCLIMATIZING"}
    altitude = _state(hass, "altitudeAcclimation")
    assert altitude.state == "1200"
    assert _extra(altitude) == {"trend": None, "current_altitude": 1500}


@pytest.mark.parametrize("garmin_data", [{"training": {}}], indirect=True)
async def test_vo2_max_unknown_when_missing(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    assert _state(hass, "vo2Max").state == STATE_UNKNOWN


# ── Body ──────────────────────────────────────────────────────────────────────


async def test_weight_uses_kg_and_utc_weigh_in_time(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Weight uses ha-garmin's 'weightKg'; measurement_time is timestampGMT, not 'date'."""
    state = _state(hass, "weightKg")
    assert state.state == "75.0"
    assert _extra(state) == {
        "measurement_time": datetime.datetime(2026, 10, 18, 13, 13, 52, tzinfo=datetime.UTC)
    }


@pytest.mark.parametrize(
    "garmin_data",
    [
        {"body": {"weightKg": 75.0, "timestampGMT": timestamp}}
        for timestamp in (None, "1792329232000", True, 1e18)
    ],
    ids=["missing", "string", "bool", "out_of_range"],
    indirect=True,
)
async def test_weight_without_usable_timestamp_has_no_measurement_time(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """A weigh-in without a usable timestampGMT leaves the attribute out instead of raising."""
    state = _state(hass, "weightKg")
    assert _extra(state) == {}
    assert state.state == "75.0"


async def test_fitness_age_vigorous_factors(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Vigorous days/minutes per week come from fitness-age's components."""
    days = _state(hass, "vigorousDaysAvg")
    assert days.state == "0.3"
    assert _extra(days) == {
        "target": 3,
        "potential_fitness_age": 54.0,
        "weeks_averaged": 6,
        "stale": False,
    }
    minutes = _state(hass, "vigorousMinutesAvg")
    assert minutes.state == "5.6"
    assert minutes.attributes["target"] == 75


@pytest.mark.parametrize(
    "garmin_data",
    [
        {"body": data}
        for data in ({}, {"components": None}, {"components": {"vigorousDaysAvg": None}})
    ],
    ids=["no_components", "null_components", "null_factor"],
    indirect=True,
)
async def test_fitness_age_vigorous_factors_missing(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    state = _state(hass, "vigorousDaysAvg")
    assert state.state == STATE_UNKNOWN
    assert _extra(state) == {}


# ── Goals ─────────────────────────────────────────────────────────────────────


async def test_badges_returns_count(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    assert _state(hass, "badges").state == "1"


@pytest.mark.parametrize(
    "garmin_data",
    [
        {
            "goals": {
                "badges": [
                    {"badgeName": "Old", "badgeEarnedDate": "2024-01-01T00:00:00"},
                    {"badgeName": "Unknown", "badgeEarnedDate": None},
                    {"badgeName": "New", "badgeEarnedDate": "2025-06-01T00:00:00"},
                ]
            }
        }
    ],
    indirect=True,
)
async def test_badges_sort_tolerates_missing_earned_date(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """A badge with a null badgeEarnedDate must not break attribute rendering."""
    state = _state(hass, "badges")
    assert state.state == "3"
    badges = state.attributes["badges"]
    assert [b["name"] for b in badges] == ["New", "Old", "Unknown"]
    assert badges[2]["earned_date"] is None


# ── Activity ──────────────────────────────────────────────────────────────────


async def test_last_activity_and_recent_activities(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """lastActivity: state = name; lastActivities counts only the last 7 days."""
    last = _state(hass, "lastActivity")
    assert last.state == "Morning Run"
    assert last.attributes["activityId"] == 12345
    # Fixture has one activity 1 day old and one 30 days old.
    recent = _state(hass, "lastActivities")
    assert recent.state == "1"
    assert len(recent.attributes["last_activities"]) == 2


async def test_training_plan_goal_event_countdown(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """trainingPlanGoalEvent: state = eventName, attributes = the event plus a countdown."""
    freezer.move_to("2026-11-01T12:00:00+00:00")
    await _push(hass, entry, mock_client, "activity", mock_activity_data())
    state = _state(hass, "trainingPlanGoalEvent")
    assert state.state == "5K Plan"
    assert _extra(state) == {
        **mock_activity_data()["trainingPlanGoalEvent"],
        "days_until_event": 20,
    }

    # Negative after the race.
    freezer.move_to("2026-11-23T12:00:00+00:00")
    await _push(hass, entry, mock_client, "activity", mock_activity_data())
    assert _state(hass, "trainingPlanGoalEvent").attributes["days_until_event"] == -2


async def test_training_plan_goal_event_countdown_tolerates_bad_date(
    hass: HomeAssistant, entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    await _push(
        hass,
        entry,
        mock_client,
        "activity",
        {"trainingPlanGoalEvent": {"eventName": "Race", "date": None}},
    )
    assert _state(hass, "trainingPlanGoalEvent").attributes["days_until_event"] is None
    await _push(hass, entry, mock_client, "activity", {"trainingPlanGoalEvent": {}})
    assert _extra(_state(hass, "trainingPlanGoalEvent")) == {}


async def test_upcoming_events_count_and_countdowns(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """upcomingEvents: state = event count, each event gets a countdown."""
    freezer.move_to("2026-11-01T12:00:00+00:00")
    await _push(hass, entry, mock_client, "activity", mock_activity_data())
    state = _state(hass, "upcomingEvents")
    assert state.state == "2"
    events = state.attributes["events"]
    assert [e["eventName"] for e in events] == ["5K Plan", "City Marathon"]
    assert events[0]["days_until_event"] == 20

    await _push(hass, entry, mock_client, "activity", {"upcomingEvents": None})
    state = _state(hass, "upcomingEvents")
    assert state.state == "0"
    assert _extra(state) == {"events": []}


_WORKOUT_STEPS = [
    {"stepOrder": 1, "stepType": "warmup", "endCondition": "lap.button"},
    {
        "stepOrder": 2,
        "stepType": "interval",
        "endCondition": "distance",
        "endConditionValue": 4828.02,
        "targetType": "heart.rate.zone",
        "targetValueOne": 141.0,
        "targetValueTwo": 159.0,
    },
]


def _activity_with_steps() -> dict[str, Any]:
    data = mock_activity_data()
    data["todayScheduledWorkout"]["workoutSteps"] = _WORKOUT_STEPS
    data["nextScheduledWorkout"]["workoutSteps"] = _WORKOUT_STEPS
    return data


@pytest.mark.parametrize("garmin_data", [{"activity": _activity_with_steps()}], indirect=True)
async def test_scheduled_workout_sensors_add_steps_summary(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Today's and the next workout expose a readable line per step."""
    for key in ("todayScheduledWorkout", "nextScheduledWorkout"):
        state = _state(hass, key)
        assert state.state == "Benchmark Run"
        assert state.attributes["workoutSteps"] == _WORKOUT_STEPS
        assert state.attributes["steps_summary"] == [
            "Warm-up until lap press",
            "Interval 4.83 km @ 141–159 bpm",
        ]


async def test_scheduled_workout_without_steps_has_no_summary(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    assert "steps_summary" not in _state(hass, "todayScheduledWorkout").attributes


# ── Blood pressure ────────────────────────────────────────────────────────────


async def test_blood_pressure_sensors(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """bpSystolic carries diastolic and pulse; the category is its readable name."""
    systolic = _state(hass, "bpSystolic")
    assert systolic.state == "120"
    assert systolic.attributes["diastolic"] == 80
    assert systolic.attributes["pulse"] == 70
    assert _state(hass, "bpCategoryName").state == "Normal"


# ── Gear coordinator: alarm, solar, devices ──────────────────────────────────


async def test_gear_coordinator_sensors(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Next alarm, solar intensity and device list from the default gear data."""
    assert _state(hass, "nextAlarm").state == "2026-01-25T06:30:00+00:00"

    solar = _state(hass, "solarIntensity")
    assert solar.state == "42.5"
    assert solar.attributes["devices"][0]["deviceName"] == "Instinct 2X Solar"

    devices = _state(hass, "devices")
    assert devices.state == "1"
    assert devices.attributes["devices"][0]["productDisplayName"] == "Instinct 2X Solar"
    assert devices.attributes["devices"][0]["serialNumber"] == "ABC123456"
    assert devices.attributes["last_used_device"]["lastUsedDeviceName"] == "Instinct 2X Solar"


@pytest.mark.parametrize(
    ("garmin_data", "expected"),
    [
        ({"gear": {"nextAlarm": []}}, STATE_UNKNOWN),
        ({"gear": {"nextAlarm": None}}, STATE_UNKNOWN),
        ({"gear": {}}, STATE_UNKNOWN),
        ({"gear": {"nextAlarm": ["garbage"]}}, STATE_UNKNOWN),
        (
            {"gear": {"nextAlarm": ["not-a-timestamp", "2026-01-25T06:30:00+00:00"]}},
            "2026-01-25T06:30:00+00:00",
        ),
    ],
    ids=["empty", "null", "missing", "all_unparsable", "skips_unparsable"],
    indirect=["garmin_data"],
)
async def test_next_alarm_edge_cases(
    hass: HomeAssistant, entry: MockConfigEntry, expected: str
) -> None:
    """An unparsable alarm is skipped; without a usable alarm the state is unknown."""
    assert _state(hass, "nextAlarm").state == expected


@pytest.mark.parametrize(
    ("garmin_data", "key", "expected"),
    [
        ({"gear": {"solarIntensity": []}}, "solarIntensity", STATE_UNKNOWN),
        ({"gear": {}}, "solarIntensity", STATE_UNKNOWN),
        ({"gear": {}}, "devices", STATE_UNKNOWN),
        ({"gear": {"devices": []}}, "devices", "0"),
    ],
    ids=["no_solar_devices", "solar_missing", "devices_missing", "devices_empty"],
    indirect=["garmin_data"],
)
async def test_solar_and_devices_without_data(
    hass: HomeAssistant, entry: MockConfigEntry, key: str, expected: str
) -> None:
    assert _state(hass, key).state == expected


# ── Menstrual ─────────────────────────────────────────────────────────────────


@enable_all
async def test_menstrual_sensors(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Dates are parsed; cycle day and phase carry the day log and summary."""
    assert _state(hass, "menstrualCycleStart").state == "2026-01-20"
    assert _state(hass, "menstrualFertileWindowStart").state == "2026-01-21"
    assert _state(hass, "menstrualFertileWindowEnd").state == "2026-01-27"

    day = _state(hass, "menstrualCycleDay")
    assert day.state == "18"
    attrs = day.attributes
    assert attrs["calendar_date"] == "2026-06-01"
    assert attrs["symptoms"] == ["ACNE"]
    assert attrs["moods"] == ["FINE"]
    assert attrs["flow"] == "HEAVY"
    assert attrs["notes"] == "Some note"
    assert attrs["ovulation_day"] is True
    assert attrs["has_baby_movement"] is False

    phase = _state(hass, "menstrualCyclePhase")
    assert phase.state == "luteal"
    attrs = phase.attributes
    assert attrs["day_in_cycle"] == 18
    assert attrs["period_length"] == 4
    assert attrs["length_of_current_phase"] == 12
    assert attrs["predicted_cycle_length"] == 28
    assert attrs["cycle_type"] == "REGULAR"


@enable_all
@pytest.mark.parametrize(
    ("garmin_data", "key"),
    [
        (
            {"menstrual": {"menstrualData": {"daySummary": _day_summary(fertileWindowStart=0)}}},
            "menstrualFertileWindowStart",
        ),
        (
            {"menstrual": {"menstrualData": {"daySummary": _day_summary(fertileWindowStart=0)}}},
            "menstrualFertileWindowEnd",
        ),
        (
            {
                "menstrual": {
                    "menstrualData": {
                        "daySummary": _day_summary(fertileWindowStart=5, lengthOfFertileWindow=0)
                    }
                }
            },
            "menstrualFertileWindowEnd",
        ),
    ],
    ids=["start_no_window_start", "end_no_window_start", "end_no_window_length"],
    indirect=["garmin_data"],
)
async def test_menstrual_fertile_window_unknown_without_window(
    hass: HomeAssistant, entry: MockConfigEntry, key: str
) -> None:
    """No fertile window date when Garmin reports its start or length as 0."""
    assert _state(hass, key).state == STATE_UNKNOWN


@enable_all
@pytest.mark.parametrize(
    "garmin_data",
    [
        {"menstrual": {"menstrualData": {"daySummary": summary}}}
        for summary in (
            {"fertileWindowStart": 2, "lengthOfFertileWindow": 5},
            {"fertileWindowStart": 2, "lengthOfFertileWindow": 5, "startDate": "20-01-2026"},
        )
    ],
    ids=["no_start_date", "malformed_start_date"],
    indirect=True,
)
async def test_menstrual_dates_unknown_without_a_usable_cycle_start(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Cycle start and fertile window dates are unknown when the cycle start is unusable."""
    for key in ("menstrualCycleStart", "menstrualFertileWindowStart", "menstrualFertileWindowEnd"):
        assert _state(hass, key).state == STATE_UNKNOWN, key


@enable_all
@pytest.mark.parametrize(
    "garmin_data",
    [{"menstrual": {"menstrualData": {"daySummary": _day_summary(fertileWindowStart=None)}}}],
    indirect=True,
)
async def test_menstrual_cycle_day_attributes_empty_without_day_log(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    state = _state(hass, "menstrualCycleDay")
    assert state.state == "18"
    assert _extra(state) == {}


_CALENDAR_NO_PREDICTION = {
    "menstrualData": {"daySummary": _day_summary(fertileWindowStart=None)},
    "menstrualCalendar": {
        "cycleSummaries": [
            {
                "startDate": "2026-11-29",
                "periodLength": 5,
                "fertileWindowStart": 9,
                "lengthOfFertileWindow": 5,
                "educationContentMod": 9,
                "predictedCycle": False,
            }
        ]
    },
}
_CALENDAR_MALFORMED_PREDICTION = {
    "menstrualCalendar": {
        "cycleSummaries": [
            {"predictedCycle": True, "startDate": "14/02/2026"},
            {"predictedCycle": True, "startDate": "2026-03-14"},
        ]
    }
}


@enable_all
@pytest.mark.parametrize(
    ("now", "data", "expected"),
    [
        ("2026-01-01T12:00:00+00:00", mock_menstrual_data(), "2026-02-14"),
        ("2026-06-01T12:00:00+00:00", mock_menstrual_data(), STATE_UNKNOWN),
        ("2026-01-01T12:00:00+00:00", _CALENDAR_NO_PREDICTION, STATE_UNKNOWN),
        ("2026-01-01T12:00:00+00:00", _CALENDAR_MALFORMED_PREDICTION, "2026-03-14"),
    ],
    ids=["future", "all_in_the_past", "none_predicted", "skips_malformed_dates"],
)
async def test_menstrual_next_predicted_cycle_start(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    now: str,
    data: dict[str, Any],
    expected: str,
) -> None:
    """The earliest predicted cycle from today on; malformed dates are skipped."""
    freezer.move_to(now)
    await _push(hass, entry, mock_client, "menstrual", data)
    assert _state(hass, "menstrualNextPredictedCycleStart").state == expected


# ── Recorder: oversized attributes (#549) ─────────────────────────────────────


def _route(points: int) -> dict[str, Any]:
    return {
        "lastActivity": {
            "polyline": [
                {"lat": 19.4326 + i / 100000, "lon": -99.1332 + i / 100000} for i in range(points)
            ],
            "hasPolyline": True,
            "activityName": "Morning Ride",
        }
    }


@pytest.mark.parametrize("garmin_data", [{"activity": _route(500)}], indirect=True)
async def test_route_polyline_never_reaches_the_recorder(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """The polyline must be excluded from what the recorder persists, siblings kept (#549)."""
    recorded = _recorded_attributes(_state(hass, "lastActivityRoute"))

    # The `!= b"{}"` assert carries the weight: when the row blows the size cap the
    # recorder drops every attribute, so checking only that the polyline is absent
    # would pass on the unfixed code too — for the wrong reason.
    assert recorded != b"{}"
    attrs = json.loads(recorded)
    # Compare keys, not raw bytes: "has_polyline" contains "polyline".
    assert "polyline" not in attrs
    assert attrs["has_polyline"] is True
    assert attrs["activity_name"] == "Morning Ride"


@pytest.mark.parametrize("garmin_data", [{"activity": _route(2000)}], indirect=True)
async def test_route_recorded_attributes_stay_under_the_16kib_cap(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Recorded attributes must fit the recorder's hard 16 KiB limit (#549)."""
    recorded = _recorded_attributes(_state(hass, "lastActivityRoute"))
    assert recorded != b"{}"
    assert len(recorded) < 16384


@pytest.mark.parametrize("garmin_data", [{"activity": _route(10)}], indirect=True)
async def test_route_polyline_remains_available_live(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """The polyline must stay on the live entity for the map card and templates."""
    state = _state(hass, "lastActivityRoute")
    assert len(state.attributes["polyline"]) == 10
    assert state.state == "10"


@pytest.mark.parametrize(
    ("garmin_data", "key", "dropped"),
    [
        (
            {
                "activity": {
                    "workouts": [
                        {"workoutName": f"W{i}", "description": "x" * 2000} for i in range(10)
                    ]
                }
            },
            "lastWorkouts",
            "last_workouts",
        ),
        (
            {
                "activity": {
                    "nextScheduledWorkout": {
                        "title": "Intervals",
                        "workoutSteps": [
                            {"stepOrder": i, "description": "x" * 500} for i in range(40)
                        ],
                    },
                    "scheduledWorkouts": [
                        {"title": f"S{i}", "notes": "x" * 1000} for i in range(30)
                    ],
                }
            },
            "nextScheduledWorkout",
            "upcoming",
        ),
    ],
    ids=["last_workouts", "next_scheduled_workout"],
    indirect=["garmin_data"],
)
async def test_workout_lists_never_reach_the_recorder(
    hass: HomeAssistant, entry: MockConfigEntry, key: str, dropped: str
) -> None:
    """Large workout attributes stay live-only so the recorder keeps the rest."""
    state = _state(hass, key)
    assert dropped in state.attributes

    recorded = _recorded_attributes(state)

    assert len(recorded) < 16384
    attrs = json.loads(recorded)
    assert dropped not in attrs
    assert "workoutSteps" not in attrs
    # Smaller siblings still record; an over-cap row would have dropped them all.
    expected = _extra(state).keys() - {dropped, "workoutSteps"}
    assert expected <= attrs.keys()
    assert attrs[ATTR_FRIENDLY_NAME]


# ── Sleep duration entity_id migration ────────────────────────────────────────


async def test_sleep_duration_migration_renames_legacy_entity_id(
    hass: HomeAssistant, prepared_entry: MockConfigEntry
) -> None:
    """The legacy '_2' sleep duration entity is renamed to the plain entity_id."""
    _register(
        hass,
        prepared_entry,
        "measurableAsleepDurationMinutes",
        "garmin_connect_sleep_duration_2",
    )
    await _setup(hass, prepared_entry)

    registry = er.async_get(hass)
    assert registry.async_get("sensor.garmin_connect_sleep_duration_2") is None
    renamed = registry.async_get("sensor.garmin_connect_sleep_duration")
    assert renamed.unique_id == _uid("measurableAsleepDurationMinutes")
    assert hass.states.get("sensor.garmin_connect_sleep_duration").state == "430"


async def test_sleep_duration_migration_skips_when_no_legacy_entity(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Without a legacy '_2' entity, the sensor is created under the plain entity_id."""
    assert _entity_id(hass, "measurableAsleepDurationMinutes") == (
        "sensor.garmin_connect_sleep_duration"
    )
    assert er.async_get(hass).async_get("sensor.garmin_connect_sleep_duration_2") is None


async def test_sleep_duration_migration_tolerates_registry_rejection(
    hass: HomeAssistant, prepared_entry: MockConfigEntry
) -> None:
    """If the target entity_id is taken the rename is skipped instead of failing setup."""
    _register(
        hass,
        prepared_entry,
        "measurableAsleepDurationMinutes",
        "garmin_connect_sleep_duration_2",
    )
    _register(hass, prepared_entry, "someOtherSensor", "garmin_connect_sleep_duration")
    await _setup(hass, prepared_entry)

    assert _entity_id(hass, "measurableAsleepDurationMinutes") == (
        "sensor.garmin_connect_sleep_duration_2"
    )
    assert hass.states.get("sensor.garmin_connect_sleep_duration_2").state == "430"


# ── Gear sensors ──────────────────────────────────────────────────────────────


async def test_gear_sensor_value_and_attributes(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """One gear sensor per item: total distance, gear details as attributes."""
    assert _entity_id(hass, "gear_gear-uuid-1") == "sensor.garmin_connect_running_shoes"
    state = _state(hass, "gear_gear-uuid-1")
    assert state.state == "500000.0"
    assert state.attributes[ATTR_FRIENDLY_NAME] == "Garmin Connect Running Shoes"
    attrs = state.attributes
    assert attrs["gear_uuid"] == "gear-uuid-1"
    assert attrs["total_activities"] == 50
    assert attrs["gear_make_name"] == "Nike"
    assert attrs["default_for_activity"] == ["running"]
    assert attrs["total_duration_seconds"] == 180000
    assert attrs["days_used"] == 45
    assert attrs["notes"] == "Race shoes"


@pytest.mark.parametrize(
    "data",
    [None, {"gearStats": [{"gearName": "No uuid", "totalActivities": 3}]}],
    ids=["no_data", "uuid_not_listed"],
)
async def test_gear_sensor_unknown_without_matching_gear(
    hass: HomeAssistant, entry: MockConfigEntry, mock_client: MagicMock, data: dict | None
) -> None:
    """Without data, or with the gear's UUID no longer listed, value and attributes are empty."""
    await _push(hass, entry, mock_client, "gear", data)
    state = _state(hass, "gear_gear-uuid-1")
    assert state.state == STATE_UNKNOWN
    assert _extra(state) == {}


@pytest.mark.parametrize(
    "garmin_data",
    [{"gear": _gear({"uuid": "abc-123", "gearName": None}, {"uuid": "def-456"})}],
    indirect=True,
)
async def test_unnamed_gear_unique_ids_do_not_collide(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Unnamed gear is 'Unknown', and its unique_id is keyed on the UUID, not the name."""
    assert _registered(hass, "gear_") == {"gear_abc-123", "gear_def-456"}
    assert _state(hass, "gear_abc-123").attributes[ATTR_FRIENDLY_NAME] == "Garmin Connect Unknown"
    assert _state(hass, "gear_def-456").attributes[ATTR_FRIENDLY_NAME] == "Garmin Connect Unknown"


@pytest.mark.parametrize(
    "garmin_data",
    [{"gear": _gear({"uuid": "g1", "gearName": "Old shoes", "totalDistance": 10})}],
    indirect=True,
)
async def test_gear_sensor_name_follows_a_rename(
    hass: HomeAssistant, entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """A gear item renamed in Garmin shows its new name on the next poll."""
    assert _state(hass, "gear_g1").attributes[ATTR_FRIENDLY_NAME] == "Garmin Connect Old shoes"

    await _push(
        hass,
        entry,
        mock_client,
        "gear",
        _gear({"uuid": "g1", "gearName": "Race shoes", "totalDistance": 12}),
    )
    state = _state(hass, "gear_g1")
    assert state.attributes[ATTR_FRIENDLY_NAME] == "Garmin Connect Race shoes"
    assert state.state == "12"
    # The entity_id stays as it was registered.
    assert state.entity_id == "sensor.garmin_connect_old_shoes"

    # Without data the last known name stays.
    await _push(hass, entry, mock_client, "gear", None)
    assert _state(hass, "gear_g1").attributes[ATTR_FRIENDLY_NAME] == "Garmin Connect Race shoes"


# ── Gear unique_id migration ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    "garmin_data", [{"gear": _gear({"uuid": "g1", "gearName": "Shoes"})}], indirect=True
)
async def test_gear_migration_renames_slug_unique_id_before_creating_entities(
    hass: HomeAssistant, prepared_entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """A legacy name-slug gear entity is re-keyed to the UUID and keeps its entity_id.

    Gear data only arrives after the platform is set up, so this also covers
    migrating on deferred data: had the entity been created first, it would be
    'sensor.garmin_connect_shoes_2' and the slug entity dropped.
    """
    _register(hass, prepared_entry, "gear_shoes", "garmin_connect_shoes")
    await _setup(hass, prepared_entry)

    registry = er.async_get(hass)
    assert registry.async_get("sensor.garmin_connect_shoes").unique_id == _uid("gear_g1")
    assert _registered(hass, "gear_") == {"gear_g1"}
    assert hass.states.get("sensor.garmin_connect_shoes").state == STATE_UNKNOWN

    # The migration runs once: a slug entity showing up later is left alone.
    _register(hass, prepared_entry, "gear_bike", "garmin_connect_bike")
    await _push(
        hass,
        prepared_entry,
        mock_client,
        "gear",
        _gear({"uuid": "g1", "gearName": "Shoes"}, {"uuid": "g2", "gearName": "Bike"}),
    )
    assert registry.async_get("sensor.garmin_connect_bike").unique_id == _uid("gear_bike")
    assert _entity_id(hass, "gear_g2") == "sensor.garmin_connect_bike_2"


@pytest.mark.parametrize(
    "garmin_data",
    [{"gear": _gear({"uuid": "abc-123", "gearName": "Trail Shoes", "totalDistance": 7})}],
    indirect=True,
)
async def test_gear_migration_collision_removes_stale_entity_instead_of_failing(
    hass: HomeAssistant, prepared_entry: MockConfigEntry
) -> None:
    """If a UUID-keyed entity already exists, the old slug entity is dropped, not fatal."""
    _register(hass, prepared_entry, "gear_trail_shoes", "garmin_connect_trail_shoes_legacy")
    _register(hass, prepared_entry, "gear_abc-123", "garmin_connect_trail_shoes")
    await _setup(hass, prepared_entry)

    assert er.async_get(hass).async_get("sensor.garmin_connect_trail_shoes_legacy") is None
    assert _registered(hass, "gear_") == {"gear_abc-123"}
    assert hass.states.get("sensor.garmin_connect_trail_shoes").state == "7"


@pytest.mark.parametrize("garmin_data", [{"gear": _gear({"gearName": "Shoes"})}], indirect=True)
async def test_gear_without_uuid_is_left_untouched(
    hass: HomeAssistant, prepared_entry: MockConfigEntry
) -> None:
    """Gear without a UUID has no target unique_id: no migration, no entity, no pruning."""
    _register(hass, prepared_entry, "gear_shoes", "garmin_connect_shoes")
    await _setup(hass, prepared_entry)
    assert _registered(hass, "gear_") == {"gear_shoes"}


# ── Dynamic gear and power-to-weight entities ─────────────────────────────────


@pytest.mark.parametrize(
    "garmin_data",
    [
        {
            "gear": _gear({"gearName": "Shoes", "uuid": "g1"}),
            "training": _training([{"sport": "cycling"}]),
        }
    ],
    indirect=True,
)
async def test_new_gear_and_sports_are_added_after_setup(
    hass: HomeAssistant, entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    assert _registered(hass, "gear_") == {"gear_g1"}
    assert _registered(hass, "ptw_") | _registered(hass, "ftp_") == {"ptw_cycling", "ftp_cycling"}

    await _push(
        hass,
        entry,
        mock_client,
        "gear",
        _gear({"gearName": "Shoes", "uuid": "g1"}, {"gearName": "Bike", "uuid": "g2"}),
    )
    await _push(
        hass,
        entry,
        mock_client,
        "training",
        _training([{"sport": "cycling"}, {"sport": "running"}]),
    )

    assert _registered(hass, "gear_") == {"gear_g1", "gear_g2"}
    assert hass.states.get("sensor.garmin_connect_bike") is not None
    assert _registered(hass, "ptw_") | _registered(hass, "ftp_") == {
        "ptw_cycling",
        "ftp_cycling",
        "ptw_running",
        "ftp_running",
    }


@pytest.mark.parametrize(
    "garmin_data",
    [{"gear": _gear({"gearName": "Shoes", "uuid": "g1"}, {"gearName": "Bike", "uuid": "g2"})}],
    indirect=True,
)
async def test_removed_gear_is_dropped_from_registry(
    hass: HomeAssistant, entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    assert hass.states.get("sensor.garmin_connect_bike") is not None

    await _push(hass, entry, mock_client, "gear", _gear({"gearName": "Shoes", "uuid": "g1"}))
    assert _registered(hass, "gear_") == {"gear_g1"}
    assert hass.states.get("sensor.garmin_connect_bike") is None

    # Gear reappearing after removal is re-added rather than considered known.
    await _push(
        hass,
        entry,
        mock_client,
        "gear",
        _gear({"gearName": "Shoes", "uuid": "g1"}, {"gearName": "Bike", "uuid": "g2"}),
    )
    assert _registered(hass, "gear_") == {"gear_g1", "gear_g2"}
    assert _state(hass, "gear_g2").state == STATE_UNKNOWN


@pytest.mark.parametrize(
    "garmin_data", [{"gear": _gear({"gearName": "Shoes", "uuid": "g1"})}], indirect=True
)
async def test_empty_gear_list_does_not_prune(
    hass: HomeAssistant, entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """A transient empty gearStats (failed gear call) must not delete every gear entity."""
    await _push(hass, entry, mock_client, "gear", {"gearStats": []})
    await _push(hass, entry, mock_client, "gear", None)
    assert _registered(hass, "gear_") == {"gear_g1"}


@pytest.mark.parametrize(
    "garmin_data", [{"gear": _gear({"gearName": "Shoes", "uuid": "g1"})}], indirect=True
)
async def test_gear_removed_while_ha_was_stopped_is_dropped_from_registry(
    hass: HomeAssistant, prepared_entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Gear sensors left in the registry for gear Garmin no longer has get removed."""
    _register(hass, prepared_entry, "gear_old", "garmin_connect_old_gear")
    _register(hass, prepared_entry, "gear_g1", "garmin_connect_shoes")
    await _setup(hass, prepared_entry)

    assert _registered(hass, "gear_") == {"gear_g1"}
    # Other sensors and the calendar of the entry are not gear and stay.
    assert _entity_id(hass, "totalSteps") is not None
    assert hass.states.get("calendar.garmin_connect_scheduled_workouts") is not None

    # The registry sweep runs once; later polls only prune gear seen this run.
    _register(hass, prepared_entry, "gear_old2", "garmin_connect_old_gear_2")
    await _push(
        hass, prepared_entry, mock_client, "gear", _gear({"gearName": "Shoes", "uuid": "g1"})
    )
    assert _registered(hass, "gear_") == {"gear_g1", "gear_old2"}


@pytest.mark.parametrize(
    "garmin_data",
    [{"training": _training([{"sport": "cycling"}, {"sport": "running"}])}],
    indirect=True,
)
async def test_power_sensors_for_a_vanished_sport_are_removed(
    hass: HomeAssistant, entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """PTW/FTP sensors of a sport no longer reported are dropped from the registry."""
    await _push(hass, entry, mock_client, "training", _training([{"sport": "cycling"}]))
    assert _registered(hass, "ptw_") | _registered(hass, "ftp_") == {"ptw_cycling", "ftp_cycling"}
    assert hass.states.get("sensor.garmin_connect_ftp_running") is None

    # An empty list is more likely a failed call than every sport gone.
    await _push(hass, entry, mock_client, "training", _training([]))
    assert _registered(hass, "ptw_") | _registered(hass, "ftp_") == {"ptw_cycling", "ftp_cycling"}


@pytest.mark.parametrize(
    "garmin_data", [{"training": _training([{"sport": "cycling"}])}], indirect=True
)
async def test_power_sensors_removed_while_ha_was_stopped_are_swept_once(
    hass: HomeAssistant, prepared_entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Registry PTW/FTP sensors for sports Garmin no longer reports are removed once."""
    _register(hass, prepared_entry, "ptw_swimming", "garmin_connect_power_to_weight_swimming")
    _register(hass, prepared_entry, "ftp_swimming", "garmin_connect_ftp_swimming")
    _register(hass, prepared_entry, "ptw_cycling", "garmin_connect_power_to_weight_cycling")
    await _setup(hass, prepared_entry)

    assert _registered(hass, "ptw_") | _registered(hass, "ftp_") == {"ptw_cycling", "ftp_cycling"}

    _register(hass, prepared_entry, "ptw_rowing", "garmin_connect_power_to_weight_rowing")
    await _push(hass, prepared_entry, mock_client, "training", _training([{"sport": "cycling"}]))
    assert "ptw_rowing" in _registered(hass, "ptw_")


# ── Power-to-weight / FTP sensors ─────────────────────────────────────────────


@pytest.mark.parametrize(
    "garmin_data",
    [
        {
            "training": _training(
                [{"sport": "cross_country_skiing"}, {"sport": "cycling"}, {"sport": "running"}]
            )
        }
    ],
    indirect=True,
)
async def test_power_sensor_entity_ids_include_sport(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """The entity_id carries the sport (#585), so sports of one type never collide.

    Translation placeholders aren't resolved by HA's default suggested_object_id,
    so the integration supplies one.
    """
    assert _entity_id(hass, "ptw_cross_country_skiing") == (
        "sensor.garmin_connect_power_to_weight_cross_country_skiing"
    )
    assert _entity_id(hass, "ftp_cycling") == "sensor.garmin_connect_ftp_cycling"
    ftp_ids = {_entity_id(hass, f"ftp_{s}") for s in ("running", "cycling", "cross_country_skiing")}
    assert len(ftp_ids) == 3
    assert _state(hass, "ptw_cross_country_skiing").attributes[ATTR_FRIENDLY_NAME] == (
        "Garmin Connect Power to Weight Cross Country Skiing"
    )


_PTW_ENTRY = {
    "sport": "cycling",
    "powerToWeight": 3.85,
    "functionalThresholdPower": 270,
    "weight": 70.1,
    "calendarDate": "2026-01-20",
    "ftpCreateTime": "2026-01-10T08:00:00",
    "weightCreateTime": "2026-01-19T07:00:00",
    "isStale": False,
}
_PTW_COMMON = {
    "sport": "cycling",
    "weight_kg": 70.1,
    "calendar_date": "2026-01-20",
    "ftp_created": "2026-01-10T08:00:00",
    "weight_created": "2026-01-19T07:00:00",
    "is_stale": False,
}


@pytest.mark.parametrize(
    "garmin_data",
    [{"training": _training([{"sport": "running", "powerToWeight": 1.0}, _PTW_ENTRY])}],
    indirect=True,
)
async def test_power_sensor_value_and_attributes(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Each power sensor reports its own metric and exposes the other one as an attribute."""
    ptw = _state(hass, "ptw_cycling")
    assert ptw.state == "3.85"
    assert ptw.attributes[ATTR_UNIT_OF_MEASUREMENT] == "W/kg"
    assert _extra(ptw) == {**_PTW_COMMON, "ftp": 270}

    ftp = _state(hass, "ftp_cycling")
    assert ftp.state == "270"
    assert ftp.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.POWER
    assert _extra(ftp) == {**_PTW_COMMON, "power_to_weight": 3.85}


@pytest.mark.parametrize("garmin_data", [{"training": _training([_PTW_ENTRY])}], indirect=True)
@pytest.mark.parametrize(
    "data",
    [None, {"powerToWeight": None}, {"powerToWeight": [{"sport": None}]}],
    ids=["no_data", "null_list", "sport_missing"],
)
async def test_power_sensor_unknown_without_entry_for_sport(
    hass: HomeAssistant, entry: MockConfigEntry, mock_client: MagicMock, data: dict | None
) -> None:
    """A power sensor whose sport is absent reports unknown with no attributes."""
    await _push(hass, entry, mock_client, "training", data)
    for suffix in ("ptw_cycling", "ftp_cycling"):
        state = _state(hass, suffix)
        assert state.state == STATE_UNKNOWN
        assert _extra(state) == {}


async def test_gear_sensor_survives_null_gear_stats(
    hass: HomeAssistant, entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Garmin sending gearStats: null must not break gear state updates."""
    assert _state(hass, "gear_gear-uuid-1").state != STATE_UNAVAILABLE

    await _push(hass, entry, mock_client, "gear", {"gearStats": None})

    state = _state(hass, "gear_gear-uuid-1")
    assert state.state == STATE_UNKNOWN
    assert "gear_uuid" not in state.attributes


@pytest.mark.parametrize(
    "garmin_data",
    [{"training": _training([{"sport": "Cycling", "powerToWeight": 3.1}])}],
    indirect=True,
)
async def test_power_sensor_survives_sport_recasing(
    hass: HomeAssistant, entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """A sport Garmin re-cases is the same sport: no duplicate entities, value kept."""
    before = _registered(hass, "ptw_") | _registered(hass, "ftp_")
    assert before == {"ptw_cycling", "ftp_cycling"}

    await _push(
        hass,
        entry,
        mock_client,
        "training",
        _training([{"sport": "cycling", "powerToWeight": 3.4}]),
    )

    assert _registered(hass, "ptw_") | _registered(hass, "ftp_") == before
    assert float(_state(hass, "ptw_cycling").state) == 3.4

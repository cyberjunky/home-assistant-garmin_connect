"""Tests for Garmin Connect services, called through Home Assistant's service registry."""

from datetime import date, datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, create_autospec, patch

import probatio as vol
import pytest
import yaml
from ha_garmin import GarminClient, GarminConnectError
from homeassistant.core import HomeAssistant, ServiceResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from pytest_homeassistant.common import MockConfigEntry

from custom_components.garmin_connect.const import DOMAIN
from custom_components.garmin_connect.services import (
    ADD_BLOOD_PRESSURE_SCHEMA,
    ADD_BODY_COMPOSITION_SCHEMA,
    ADD_GEAR_TO_ACTIVITY_SCHEMA,
    ADD_HYDRATION_SCHEMA,
    ADD_NUTRITION_SCHEMA,
    CREATE_ACTIVITY_SCHEMA,
    CREATE_WORKOUT_SCHEMA,
    DELETE_WORKOUT_SCHEMA,
    DOWNLOAD_ACTIVITY_SCHEMA,
)

from .conftest import (
    ENTRY_DATA,
    mock_activity_data,
    mock_blood_pressure_data,
    mock_body_data,
    mock_core_data,
    mock_gear_data,
    mock_goals_data,
    mock_menstrual_data,
    mock_nutrition_data,
    mock_training_data,
)

SERVICES_YAML = Path(__file__).parent.parent / "custom_components/garmin_connect/services.yaml"

_WORKOUT = {"workoutName": "Easy", "sportType": {"sportTypeKey": "running"}}
_GEAR_UUID = "gear-uuid-1"


async def _call(
    hass: HomeAssistant,
    service: str,
    data: dict[str, Any],
    *,
    return_response: bool = False,
) -> ServiceResponse:
    """Call a Garmin Connect action the way an automation or the UI would."""
    return await hass.services.async_call(
        DOMAIN, service, data, blocking=True, return_response=return_response
    )


def _entity_id(hass: HomeAssistant, entry: MockConfigEntry, key: str) -> str:
    """Return the entity ID of an entry's sensor by its description key."""
    entity_id = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_{key}")
    assert entity_id is not None, key
    return entity_id


def _gear_entity_id(hass: HomeAssistant, entry: MockConfigEntry) -> str:
    """Return the entity ID of the entry's gear sensor."""
    return _entity_id(hass, entry, f"gear_{_GEAR_UUID}")


@pytest.fixture
async def config_dir(hass: HomeAssistant, tmp_path: Path) -> Path:
    """Use an empty temporary config directory with no external dirs allowlisted."""
    config = tmp_path / "config"
    config.mkdir()
    hass.config.config_dir = str(config)
    hass.config.allowlist_external_dirs = set()
    return config


@pytest.fixture
async def second_account(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> tuple[MockConfigEntry, MagicMock]:
    """Set up a second Garmin account with its own ha-garmin client."""
    client = create_autospec(GarminClient, instance=True)
    for method, data in (
        ("fetch_core_data", mock_core_data),
        ("fetch_activity_data", mock_activity_data),
        ("fetch_training_data", mock_training_data),
        ("fetch_body_data", mock_body_data),
        ("fetch_goals_data", mock_goals_data),
        ("fetch_gear_data", mock_gear_data),
        ("fetch_blood_pressure_data", mock_blood_pressure_data),
        ("fetch_menstrual_data", mock_menstrual_data),
        ("fetch_nutrition_data", mock_nutrition_data),
    ):
        setattr(client, method, AsyncMock(return_value=data()))
    client.today.return_value = date(2026, 1, 15)

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="other@example.com",
        data=dict(ENTRY_DATA),
        unique_id="987654321",
        entry_id="second_entry_id",
    )
    entry.add_to_hass(hass)
    with patch("custom_components.garmin_connect.GarminClient", return_value=client):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
    return entry, client


# ── Registration and account resolution ─────────────────────────────────────


async def test_setup_registers_all_services(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Setting up the integration registers all 15 actions."""
    assert set(hass.services.async_services_for_domain(DOMAIN)) == {
        "set_active_gear",
        "add_body_composition",
        "add_blood_pressure",
        "create_activity",
        "upload_activity",
        "download_activity",
        "add_gear_to_activity",
        "add_hydration",
        "add_nutrition_log",
        "create_workout",
        "update_workout",
        "delete_workout",
        "schedule_workout",
        "unschedule_workout",
        "get_day_summary",
    }


@pytest.mark.usefixtures("ha_environment")
async def test_service_no_entry_raises(hass: HomeAssistant) -> None:
    """Actions exist without a config entry but refuse to run."""
    assert await async_setup_component(hass, DOMAIN, {})

    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, "add_body_composition", {"weight": 80.0})
    assert err.value.translation_key == "no_integration_configured"


@pytest.mark.usefixtures("ha_environment", "mock_auth")
async def test_service_entry_not_loaded_raises(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """An entry that failed to set up has no client to call."""
    mock_client.fetch_core_data.side_effect = GarminConnectError("down")
    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)

    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, "add_body_composition", {"weight": 80.0})
    assert err.value.translation_key == "integration_not_loaded"
    mock_client.add_body_composition.assert_not_awaited()


async def test_service_multiple_entries_without_entity_id_raises(
    hass: HomeAssistant,
    mock_client: MagicMock,
    second_account: tuple[MockConfigEntry, MagicMock],
) -> None:
    """With two accounts an action must say which one via entity_id."""
    _, second_client = second_account

    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, "add_body_composition", {"weight": 80.0})
    assert err.value.translation_key == "ambiguous_account"
    mock_client.add_body_composition.assert_not_awaited()
    second_client.add_body_composition.assert_not_awaited()


async def test_entity_not_in_registry_raises(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """An entity_id that is not registered does not fall back to an account."""
    with pytest.raises(ServiceValidationError) as err:
        await _call(
            hass, "add_body_composition", {"entity_id": "sensor.missing_weight", "weight": 80.0}
        )
    assert err.value.translation_key == "entity_not_found"
    mock_client.add_body_composition.assert_not_awaited()


async def test_entity_of_another_integration_raises(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """An entity owned by a non-Garmin config entry must not fall back to an account."""
    other_entry = MockConfigEntry(domain="other")
    other_entry.add_to_hass(hass)
    other = er.async_get(hass).async_get_or_create(
        "sensor", "other", "weight", config_entry=other_entry
    )

    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, "add_body_composition", {"entity_id": other.entity_id, "weight": 80.0})
    assert err.value.translation_key == "entity_not_found"
    mock_client.add_body_composition.assert_not_awaited()


async def test_add_body_composition_targets_entity_config_entry(
    hass: HomeAssistant,
    mock_client: MagicMock,
    second_account: tuple[MockConfigEntry, MagicMock],
) -> None:
    """add_body_composition must target the account that owns entity_id."""
    entry, second_client = second_account

    await _call(
        hass,
        "add_body_composition",
        {"entity_id": _entity_id(hass, entry, "weightKg"), "weight": 72.0},
    )

    mock_client.add_body_composition.assert_not_awaited()
    second_client.add_body_composition.assert_awaited_once()
    assert second_client.add_body_composition.call_args.kwargs["weight"] == 72.0


# ── set_active_gear / add_gear_to_activity ──────────────────────────────────


async def test_set_active_gear_by_uuid(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """set_active_gear must call client with the supplied gear_uuid."""
    await _call(
        hass,
        "set_active_gear",
        {"gear_uuid": "abc-123", "activity_type": "running", "setting": "set as default"},
    )

    mock_client.set_active_gear.assert_awaited_once_with(
        activity_type="running", setting="set as default", gear_uuid="abc-123"
    )


async def test_set_active_gear_default_setting(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Without a setting the schema default makes the gear the only default."""
    await _call(hass, "set_active_gear", {"gear_uuid": "abc-123", "activity_type": "running"})

    mock_client.set_active_gear.assert_awaited_once_with(
        activity_type="running",
        setting="set this as default, unset others",
        gear_uuid="abc-123",
    )


async def test_set_active_gear_by_entity_id(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """set_active_gear must resolve gear_uuid from the gear sensor's attributes."""
    await _call(
        hass,
        "set_active_gear",
        {
            "entity_id": _gear_entity_id(hass, init_integration),
            "activity_type": "running",
            "setting": "set as default",
        },
    )

    mock_client.set_active_gear.assert_awaited_once_with(
        activity_type="running", setting="set as default", gear_uuid=_GEAR_UUID
    )


async def test_set_active_gear_by_entity_id_targets_entity_account(
    hass: HomeAssistant,
    mock_client: MagicMock,
    second_account: tuple[MockConfigEntry, MagicMock],
) -> None:
    """set_active_gear must use the account that owns the gear entity."""
    entry, second_client = second_account

    await _call(
        hass,
        "set_active_gear",
        {
            "entity_id": _gear_entity_id(hass, entry),
            "activity_type": "running",
            "setting": "set as default",
        },
    )

    mock_client.set_active_gear.assert_not_awaited()
    second_client.set_active_gear.assert_awaited_once_with(
        activity_type="running", setting="set as default", gear_uuid=_GEAR_UUID
    )


async def test_add_gear_to_activity_by_uuid(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """add_gear_to_activity must call client with gear_uuid and activity_id."""
    await _call(hass, "add_gear_to_activity", {"activity_id": 12345, "gear_uuid": "gear-abc"})

    mock_client.add_gear_to_activity.assert_awaited_once_with(
        gear_uuid="gear-abc", activity_id=12345
    )


async def test_add_gear_to_activity_by_entity(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """add_gear_to_activity must resolve uuid from the gear sensor's attributes."""
    await _call(
        hass,
        "add_gear_to_activity",
        {"activity_id": 99999, "entity_id": _gear_entity_id(hass, init_integration)},
    )

    mock_client.add_gear_to_activity.assert_awaited_once_with(
        gear_uuid=_GEAR_UUID, activity_id=99999
    )


@pytest.mark.parametrize(
    ("service", "method", "data"),
    [
        (
            "set_active_gear",
            "set_active_gear",
            {"activity_type": "running", "setting": "set as default"},
        ),
        ("add_gear_to_activity", "add_gear_to_activity", {"activity_id": 1}),
    ],
)
@pytest.mark.parametrize(
    ("entity", "translation_key"),
    [
        (None, "no_gear_specified"),
        ("sensor.garmin_nonexistent", "entity_not_found"),
        ("totalSteps", "gear_uuid_not_found"),
    ],
)
async def test_gear_resolution_errors(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    service: str,
    method: str,
    data: dict[str, Any],
    entity: str | None,
    translation_key: str,
) -> None:
    """Gear must come from gear_uuid or a gear sensor; anything else is refused."""
    if entity == "totalSteps":
        # A Garmin sensor with a state, but no gear_uuid attribute.
        data = {**data, "entity_id": _entity_id(hass, init_integration, entity)}
    elif entity is not None:
        data = {**data, "entity_id": entity}

    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, service, data)
    assert err.value.translation_key == translation_key
    getattr(mock_client, method).assert_not_awaited()


# ── Body composition, blood pressure, hydration, nutrition ──────────────────


async def test_add_body_composition(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """add_body_composition must call client with the supplied fields."""
    await _call(
        hass, "add_body_composition", {"weight": 80.5, "percent_fat": 15.0, "muscle_mass": 35.0}
    )

    mock_client.add_body_composition.assert_awaited_once()
    kwargs = mock_client.add_body_composition.call_args.kwargs
    assert kwargs["weight"] == 80.5
    assert kwargs["percent_fat"] == 15.0
    assert kwargs["muscle_mass"] == 35.0
    assert kwargs["timestamp"] is None


async def test_add_blood_pressure(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """add_blood_pressure must call client.set_blood_pressure with correct args."""
    await _call(
        hass,
        "add_blood_pressure",
        {"systolic": 120, "diastolic": 80, "pulse": 70, "notes": "Morning reading"},
    )

    mock_client.set_blood_pressure.assert_awaited_once_with(
        systolic=120, diastolic=80, pulse=70, timestamp=None, notes="Morning reading"
    )


async def test_add_blood_pressure_without_pulse(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """add_blood_pressure must allow omitting pulse, matching Garmin Connect's own app."""
    await _call(hass, "add_blood_pressure", {"systolic": 120, "diastolic": 80})

    mock_client.set_blood_pressure.assert_awaited_once_with(
        systolic=120, diastolic=80, pulse=None, timestamp=None, notes=""
    )


@pytest.mark.parametrize("value", [250.0, -150.0])
async def test_add_hydration(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock, value: float
) -> None:
    """add_hydration forwards value_in_ml; negative values subtract intake."""
    await _call(hass, "add_hydration", {"value_in_ml": value})

    mock_client.set_hydration.assert_awaited_once_with(value_in_ml=value, timestamp=None)


@pytest.mark.parametrize(
    ("timestamp", "expected"),
    [
        # A naive timestamp is HA-local wall-clock time, not the process zone.
        ("2026-01-24T10:00:00", "2026-01-24T10:00:00+03:00"),
        # An aware timestamp is forwarded unchanged.
        ("2026-01-24T10:00:00+00:00", "2026-01-24T10:00:00+00:00"),
    ],
)
async def test_add_hydration_with_timestamp(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    timestamp: str,
    expected: str,
) -> None:
    """add_hydration must forward an optional timestamp as ISO 8601 with offset."""
    await hass.config.async_set_time_zone("Europe/Istanbul")

    await _call(hass, "add_hydration", {"value_in_ml": 500.0, "timestamp": timestamp})

    mock_client.set_hydration.assert_awaited_once_with(value_in_ml=500.0, timestamp=expected)


async def test_add_nutrition_log(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """add_nutrition_log needs only calories; the name defaults to Quick Add."""
    await _call(hass, "add_nutrition_log", {"calories": 500.0})

    mock_client.add_nutrition_log.assert_awaited_once_with(
        calories=500.0, carbs=None, protein=None, fat=None, name="Quick Add", timestamp=None
    )


async def test_add_nutrition_log_all_fields(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """add_nutrition_log must forward all optional macros and fields."""
    await hass.config.async_set_time_zone("Europe/Istanbul")

    await _call(
        hass,
        "add_nutrition_log",
        {
            "calories": 650.0,
            "carbs": 80.0,
            "protein": 35.0,
            "fat": 20.0,
            "name": "Lunch",
            "timestamp": "2026-04-22T12:30:00",
        },
    )

    mock_client.add_nutrition_log.assert_awaited_once_with(
        calories=650.0,
        carbs=80.0,
        protein=35.0,
        fat=20.0,
        name="Lunch",
        timestamp="2026-04-22T12:30:00+03:00",
    )


# ── create_activity ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "start",
    [
        # Naive: wall-clock time in the activity's zone.
        "2026-01-24T08:00:00",
        # Aware: converted to wall-clock time in the activity's zone.
        "2026-01-24T07:00:00+00:00",
    ],
)
async def test_create_activity(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock, start: str
) -> None:
    """create_activity forwards all fields and formats start_datetime with milliseconds."""
    await hass.config.async_set_time_zone("Europe/Amsterdam")

    await _call(
        hass,
        "create_activity",
        {
            "activity_name": "Morning Run",
            "activity_type": "running",
            "start_datetime": start,
            "duration_min": 30,
            "distance_km": 5.0,
        },
    )

    mock_client.create_activity.assert_awaited_once_with(
        activity_name="Morning Run",
        activity_type="running",
        start_datetime="2026-01-24T08:00:00.000",
        duration_min=30,
        distance_km=5.0,
        time_zone="Europe/Amsterdam",
    )


async def test_create_activity_explicit_time_zone(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """An explicit time_zone decides the wall-clock time sent to Garmin."""
    await hass.config.async_set_time_zone("Europe/Amsterdam")

    await _call(
        hass,
        "create_activity",
        {
            "activity_name": "Run",
            "activity_type": "running",
            "start_datetime": "2026-01-24T07:00:00+00:00",
            "duration_min": 30,
            "time_zone": "America/New_York",
        },
    )

    kwargs = mock_client.create_activity.call_args.kwargs
    assert kwargs["time_zone"] == "America/New_York"
    assert kwargs["start_datetime"] == "2026-01-24T02:00:00.000"
    assert kwargs["distance_km"] == 0.0


async def test_create_activity_defaults_to_now(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """create_activity must generate a start_datetime when not supplied."""
    await _call(
        hass,
        "create_activity",
        {"activity_name": "Walk", "activity_type": "walking", "duration_min": 15},
    )

    kwargs = mock_client.create_activity.call_args.kwargs
    assert kwargs["start_datetime"] is not None
    assert kwargs["start_datetime"].endswith(".000")


# ── upload_activity ─────────────────────────────────────────────────────────


async def test_upload_activity_allowlisted_dir(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    config_dir: Path,
    tmp_path: Path,
) -> None:
    """A file outside the config dir is uploaded when its dir is allowlisted."""
    external = tmp_path / "external"
    external.mkdir()
    fit_file = external / "activity.fit"
    fit_file.write_bytes(b"fake fit data")
    hass.config.allowlist_external_dirs = {str(external)}

    await _call(hass, "upload_activity", {"file_path": str(fit_file)})

    mock_client.upload_activity.assert_awaited_once_with(str(fit_file))


async def test_upload_activity_inside_config_dir_needs_no_allowlist(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    config_dir: Path,
) -> None:
    """The config dir is not in allowlist_external_dirs by default, yet must stay uploadable."""
    (config_dir / "activity.fit").write_bytes(b"fake fit data")

    with patch.object(
        hass.config, "is_allowed_path", wraps=hass.config.is_allowed_path
    ) as is_allowed:
        await _call(hass, "upload_activity", {"file_path": "activity.fit"})

    mock_client.upload_activity.assert_awaited_once_with(str(config_dir / "activity.fit"))
    is_allowed.assert_not_called()


async def test_upload_activity_path_not_allowed_raises(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    config_dir: Path,
    tmp_path: Path,
) -> None:
    """Files outside allowlist_external_dirs must never be sent to Garmin."""
    fit_file = tmp_path / "activity.fit"
    fit_file.write_bytes(b"fake fit data")

    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, "upload_activity", {"file_path": str(fit_file)})
    assert err.value.translation_key == "path_not_allowed"
    mock_client.upload_activity.assert_not_awaited()


async def test_upload_activity_symlink_out_of_config_dir_needs_allowlist(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    config_dir: Path,
    tmp_path: Path,
) -> None:
    """A symlink inside the config dir must not bypass the allowlist for its target."""
    outside = tmp_path / "secret.fit"
    outside.write_bytes(b"fake fit data")
    (config_dir / "link.fit").symlink_to(outside)

    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, "upload_activity", {"file_path": str(config_dir / "link.fit")})
    assert err.value.translation_key == "path_not_allowed"
    mock_client.upload_activity.assert_not_awaited()


@pytest.mark.parametrize("error", [OSError("unreadable"), RuntimeError("symlink loop")])
async def test_upload_activity_unresolvable_path_not_allowed(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    config_dir: Path,
    error: Exception,
) -> None:
    """A path that cannot be resolved is refused rather than uploaded."""
    fit_file = config_dir / "activity.fit"
    fit_file.write_bytes(b"fake fit data")

    with (
        patch.object(hass.config, "is_allowed_path", wraps=hass.config.is_allowed_path) as allowed,
        patch.object(Path, "resolve", side_effect=error),
        pytest.raises(ServiceValidationError) as err,
    ):
        await _call(hass, "upload_activity", {"file_path": str(fit_file)})
    assert err.value.translation_key == "path_not_allowed"
    mock_client.upload_activity.assert_not_awaited()
    allowed.assert_not_called()


@pytest.mark.parametrize(
    ("file_name", "create", "translation_key"),
    [
        ("notes.txt", True, "unsupported_file_format"),
        ("missing.fit", False, "file_not_found"),
    ],
)
async def test_upload_activity_bad_file_raises(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    config_dir: Path,
    file_name: str,
    create: bool,
    translation_key: str,
) -> None:
    """Only existing .fit/.gpx/.tcx files are uploaded."""
    if create:
        (config_dir / file_name).write_text("hello")

    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, "upload_activity", {"file_path": str(config_dir / file_name)})
    assert err.value.translation_key == translation_key
    mock_client.upload_activity.assert_not_awaited()


async def test_upload_activity_library_error_wrapped(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    config_dir: Path,
) -> None:
    """A failed upload of a valid file surfaces as upload_activity_failed."""
    mock_client.upload_activity.side_effect = GarminConnectError("boom")
    (config_dir / "activity.fit").write_bytes(b"fake fit data")

    with pytest.raises(HomeAssistantError) as err:
        await _call(hass, "upload_activity", {"file_path": "activity.fit"})
    assert err.value.translation_key == "upload_activity_failed"
    assert not isinstance(err.value, ServiceValidationError)


# ── download_activity ───────────────────────────────────────────────────────


async def test_download_activity_default_path(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    config_dir: Path,
) -> None:
    """download_activity saves under <config>/garmin_activities and returns a response."""
    mock_client.download_activity.return_value = b"fake fit data"

    response = await _call(hass, "download_activity", {"activity_id": 12345}, return_response=True)

    mock_client.download_activity.assert_awaited_once_with(12345, "fit")
    expected = config_dir / "garmin_activities" / "activity_12345.fit"
    assert expected.read_bytes() == b"fake fit data"
    assert response == {
        "file_path": str(expected),
        "size_bytes": 13,
        "activity_id": 12345,
        "file_format": "fit",
    }


async def test_download_activity_original_gets_zip_extension(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    config_dir: Path,
) -> None:
    """The original format is saved as .zip; without return_response nothing is returned."""
    mock_client.download_activity.return_value = b"PK zip data"

    response = await _call(
        hass, "download_activity", {"activity_id": 12345, "file_format": "original"}
    )

    assert response is None
    assert (config_dir / "garmin_activities" / "activity_12345.zip").is_file()


async def test_download_activity_relative_directory_path(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    config_dir: Path,
) -> None:
    """A relative path without suffix is a directory under config, holding the default name."""
    mock_client.download_activity.return_value = b"<gpx/>"

    response = await _call(
        hass,
        "download_activity",
        {"activity_id": 7, "file_format": "gpx", "file_path": "exports"},
        return_response=True,
    )

    expected = config_dir / "exports" / "activity_7.gpx"
    assert expected.read_bytes() == b"<gpx/>"
    assert response["file_path"] == str(expected)


async def test_download_activity_allowlisted_directory_path(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    config_dir: Path,
    tmp_path: Path,
) -> None:
    """An allowlisted directory outside config is checked with the final file path."""
    mock_client.download_activity.return_value = b"<gpx/>"
    external = tmp_path / "external"
    external.mkdir()
    hass.config.allowlist_external_dirs = {str(external)}

    with patch.object(
        hass.config, "is_allowed_path", wraps=hass.config.is_allowed_path
    ) as is_allowed:
        await _call(
            hass,
            "download_activity",
            {"activity_id": 7, "file_format": "gpx", "file_path": str(external)},
        )

    expected = external / "activity_7.gpx"
    assert expected.read_bytes() == b"<gpx/>"
    is_allowed.assert_called_once_with(str(expected))


async def test_download_activity_into_config_dir_needs_no_allowlist(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    config_dir: Path,
) -> None:
    """A relative path inside the config directory is allowed, as for uploads."""
    mock_client.download_activity.return_value = b"<gpx/>"

    with patch.object(
        hass.config, "is_allowed_path", wraps=hass.config.is_allowed_path
    ) as is_allowed:
        await _call(
            hass,
            "download_activity",
            {"activity_id": 7, "file_format": "gpx", "file_path": "exports/run.gpx"},
        )

    assert (config_dir / "exports" / "run.gpx").read_bytes() == b"<gpx/>"
    is_allowed.assert_not_called()


async def test_download_activity_custom_path_not_allowed_raises(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    config_dir: Path,
    tmp_path: Path,
) -> None:
    """download_activity must refuse a custom path outside allowlist_external_dirs."""
    with pytest.raises(ServiceValidationError) as err:
        await _call(
            hass,
            "download_activity",
            {"activity_id": 12345, "file_format": "gpx", "file_path": str(tmp_path / "run.gpx")},
        )
    assert err.value.translation_key == "path_not_allowed"
    mock_client.download_activity.assert_not_awaited()


async def test_download_activity_write_failure_raises(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    config_dir: Path,
) -> None:
    """A file that can't be written raises a translated error, not a raw OSError."""
    mock_client.download_activity.return_value = b"fake fit data"
    # A regular file where the target directory should be makes mkdir fail.
    (config_dir / "garmin_activities").write_text("not a directory")

    with pytest.raises(HomeAssistantError) as err:
        await _call(hass, "download_activity", {"activity_id": 12345})
    assert err.value.translation_key == "download_activity_write_failed"
    assert not isinstance(err.value, ServiceValidationError)


# ── Library errors ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("service", "method", "data", "translation_key"),
    [
        (
            "set_active_gear",
            "set_active_gear",
            {"gear_uuid": "abc", "activity_type": "running", "setting": "set as default"},
            "set_active_gear_failed",
        ),
        (
            "add_body_composition",
            "add_body_composition",
            {"weight": 80.0},
            "add_body_composition_failed",
        ),
        (
            "add_blood_pressure",
            "set_blood_pressure",
            {"systolic": 120, "diastolic": 80, "pulse": 70},
            "add_blood_pressure_failed",
        ),
        (
            "create_activity",
            "create_activity",
            {"activity_name": "Run", "activity_type": "running", "duration_min": 30},
            "create_activity_failed",
        ),
        (
            "add_gear_to_activity",
            "add_gear_to_activity",
            {"activity_id": 1, "gear_uuid": "abc"},
            "add_gear_to_activity_failed",
        ),
        ("add_hydration", "set_hydration", {"value_in_ml": 100.0}, "add_hydration_failed"),
        ("add_nutrition_log", "add_nutrition_log", {"calories": 300.0}, "add_nutrition_failed"),
        (
            "download_activity",
            "download_activity",
            {"activity_id": 12345},
            "download_activity_failed",
        ),
        ("create_workout", "create_workout", {"workout": _WORKOUT}, "create_workout_failed"),
        (
            "update_workout",
            "update_workout",
            {"workout_id": 42, "workout": _WORKOUT},
            "update_workout_failed",
        ),
        ("delete_workout", "delete_workout", {"workout_id": 42}, "delete_workout_failed"),
        (
            "schedule_workout",
            "schedule_workout",
            {"workout_id": 42, "date": "2026-10-16"},
            "schedule_workout_failed",
        ),
        (
            "unschedule_workout",
            "unschedule_workout",
            {"schedule_id": 7},
            "unschedule_workout_failed",
        ),
    ],
)
async def test_library_errors_wrapped(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    config_dir: Path,
    service: str,
    method: str,
    data: dict[str, Any],
    translation_key: str,
) -> None:
    """Library failures surface as HomeAssistantError with the service's translation key."""
    # API errors and the library's own input checks (ValueError) alike.
    for error in (GarminConnectError("boom"), ValueError("bad")):
        getattr(mock_client, method).side_effect = error

        with pytest.raises(HomeAssistantError) as err:
            await _call(hass, service, data)
        assert err.value.translation_key == translation_key
        assert not isinstance(err.value, ServiceValidationError)
        assert err.value.__cause__ is error


# ── Schema validation through the service registry ──────────────────────────


@pytest.mark.parametrize(
    ("service", "data"),
    [
        ("add_body_composition", {"weight": 5}),
        ("add_body_composition", {"weight": 80, "timestamp": "yesterday at noon"}),
        ("add_hydration", {"value_in_ml": 20000}),
        ("create_activity", {"activity_name": "R", "activity_type": "flying", "duration_min": 1}),
        ("download_activity", {"activity_id": 1.9}),
        ("delete_workout", {"workout_id": True}),
        ("create_workout", {"workout": "not json"}),
        ("set_active_gear", {"gear_uuid": "abc"}),
    ],
)
async def test_invalid_input_rejected_before_handler(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    service: str,
    data: dict[str, Any],
) -> None:
    """The registered schema rejects bad input before anything reaches Garmin."""
    with pytest.raises(vol.Invalid):
        await _call(hass, service, data)
    assert not [c for c in mock_client.mock_calls if not c[0].startswith(("fetch_", "today"))]


async def test_get_day_summary_requires_response(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """get_day_summary only makes sense with return_response."""
    mock_client.get_daily_summary.reset_mock()

    with pytest.raises(ServiceValidationError):
        await _call(hass, "get_day_summary", {"date": "2026-10-16"})
    mock_client.get_daily_summary.assert_not_awaited()


# ── Workouts ────────────────────────────────────────────────────────────────


async def test_create_workout_returns_id_and_refreshes(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """create_workout returns the new ID and refreshes activity data."""
    mock_client.create_workout.return_value = {"workoutId": 42}
    refreshes = mock_client.fetch_activity_data.await_count

    response = await _call(hass, "create_workout", {"workout": _WORKOUT}, return_response=True)

    assert response == {"workout_id": 42}
    mock_client.create_workout.assert_awaited_once_with(_WORKOUT)
    mock_client.schedule_workout.assert_not_awaited()
    assert mock_client.fetch_activity_data.await_count == refreshes + 1


async def test_create_workout_accepts_json_string(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """A workout from a template arrives as a JSON string."""
    mock_client.create_workout.return_value = {"workoutId": 42}

    await _call(hass, "create_workout", {"workout": '{"workoutName": "Easy"}'})

    mock_client.create_workout.assert_awaited_once_with({"workoutName": "Easy"})


@pytest.mark.parametrize(
    ("return_response", "expected"),
    [
        (True, {"workout_id": 42, "schedule_id": 7, "date": "2026-10-16"}),
        (False, None),
    ],
)
async def test_create_workout_with_date_schedules_it(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    return_response: bool,
    expected: dict[str, Any] | None,
) -> None:
    """create_workout with a date also schedules it, with or without a response."""
    mock_client.create_workout.return_value = {"workoutId": 42}
    mock_client.schedule_workout.return_value = {"workoutScheduleId": 7}
    refreshes = mock_client.fetch_activity_data.await_count

    response = await _call(
        hass,
        "create_workout",
        {"workout": _WORKOUT, "date": "2026-10-16"},
        return_response=return_response,
    )

    assert response == expected
    mock_client.schedule_workout.assert_awaited_once_with(42, date(2026, 10, 16))
    assert mock_client.fetch_activity_data.await_count == refreshes + 1


@pytest.mark.parametrize(
    "data", [{"workout": _WORKOUT}, {"workout": _WORKOUT, "date": "2026-10-16"}]
)
async def test_create_workout_without_id_fails(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock, data
) -> None:
    """A create answer without workoutId fails and cannot be scheduled."""
    mock_client.create_workout.return_value = {}

    with pytest.raises(HomeAssistantError) as exc:
        await _call(hass, "create_workout", data)
    assert exc.value.translation_key == "create_workout_failed"
    mock_client.schedule_workout.assert_not_awaited()


async def test_create_workout_schedule_failure_names_created_workout(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """The workout exists after a failed schedule; say so and refresh anyway."""
    mock_client.create_workout.return_value = {"workoutId": 42}
    mock_client.schedule_workout.side_effect = GarminConnectError("boom")
    refreshes = mock_client.fetch_activity_data.await_count

    with pytest.raises(HomeAssistantError) as exc:
        await _call(hass, "create_workout", {"workout": _WORKOUT, "date": "2026-10-16"})
    assert exc.value.translation_key == "create_workout_schedule_failed"
    assert exc.value.translation_placeholders["workout_id"] == "42"
    assert mock_client.fetch_activity_data.await_count == refreshes + 1


@pytest.mark.parametrize(
    ("return_response", "expected"),
    [
        (True, {"schedule_id": 7, "workout_id": 42, "date": "2026-10-16"}),
        (False, None),
    ],
)
async def test_schedule_workout(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    return_response: bool,
    expected: dict[str, Any] | None,
) -> None:
    """schedule_workout schedules and refreshes, with or without a response."""
    mock_client.schedule_workout.return_value = {"workoutScheduleId": 7, "workout": {}}
    refreshes = mock_client.fetch_activity_data.await_count

    response = await _call(
        hass,
        "schedule_workout",
        {"workout_id": 42, "date": "2026-10-16"},
        return_response=return_response,
    )

    assert response == expected
    mock_client.schedule_workout.assert_awaited_once_with(
        workout_id=42, schedule_date=date(2026, 10, 16)
    )
    assert mock_client.fetch_activity_data.await_count == refreshes + 1


async def test_schedule_workout_without_id_fails(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """A 204/empty answer must not report success with schedule_id None."""
    mock_client.schedule_workout.return_value = {}

    with pytest.raises(HomeAssistantError) as exc:
        await _call(hass, "schedule_workout", {"workout_id": 42, "date": "2026-10-16"})
    assert exc.value.translation_key == "schedule_workout_failed"


@pytest.mark.parametrize(
    ("service", "data", "method", "kwargs"),
    [
        (
            "update_workout",
            {"workout_id": 42, "workout": _WORKOUT},
            "update_workout",
            {"workout_id": 42, "workout": _WORKOUT},
        ),
        ("delete_workout", {"workout_id": "42"}, "delete_workout", {"workout_id": 42}),
        (
            "unschedule_workout",
            {"schedule_id": 7.0},
            "unschedule_workout",
            {"scheduled_workout_id": 7},
        ),
    ],
)
async def test_workout_writes_call_client_and_refresh(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    service: str,
    data: dict[str, Any],
    method: str,
    kwargs: dict[str, Any],
) -> None:
    """Workout writes reach the client with coerced IDs and refresh activity data."""
    refreshes = mock_client.fetch_activity_data.await_count

    await _call(hass, service, data)

    getattr(mock_client, method).assert_awaited_once_with(**kwargs)
    assert mock_client.fetch_activity_data.await_count == refreshes + 1


async def test_workout_error_wrapped_without_refresh(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """A failed workout write does not refresh activity data."""
    mock_client.delete_workout.side_effect = GarminConnectError("boom")
    refreshes = mock_client.fetch_activity_data.await_count

    with pytest.raises(HomeAssistantError) as exc:
        await _call(hass, "delete_workout", {"workout_id": 42})
    assert exc.value.translation_key == "delete_workout_failed"
    assert mock_client.fetch_activity_data.await_count == refreshes


# ── Day summary ─────────────────────────────────────────────────────────────


async def test_get_day_summary_returns_date_and_summary(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """get_day_summary returns the requested date with the mapped and raw summary."""
    mock_client.get_daily_summary.return_value = {"totalSteps": 12000}

    response = await _call(hass, "get_day_summary", {"date": "2026-10-16"}, return_response=True)

    assert response["date"] == "2026-10-16"
    assert response["raw"] == {"totalSteps": 12000}
    assert response["summary"]["totalSteps"] == 12000
    mock_client.get_daily_summary.assert_awaited_with(date(2026, 10, 16))


async def test_get_day_summary_error_wrapped(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """get_day_summary wraps library failures in get_day_summary_failed."""
    for error in (GarminConnectError("boom"), ValueError("bad")):
        mock_client.get_daily_summary.side_effect = error

        with pytest.raises(HomeAssistantError) as err:
            await _call(hass, "get_day_summary", {"date": "2026-10-16"}, return_response=True)
        assert err.value.translation_key == "get_day_summary_failed"
        assert not isinstance(err.value, ServiceValidationError)
        assert err.value.__cause__ is error


# ── Schemas (pure validation) ───────────────────────────────────────────────


@pytest.mark.parametrize(
    "schema",
    [
        ADD_BODY_COMPOSITION_SCHEMA,
        ADD_BLOOD_PRESSURE_SCHEMA,
        ADD_HYDRATION_SCHEMA,
        ADD_NUTRITION_SCHEMA,
    ],
)
def test_timestamp_must_be_a_datetime(schema: vol.Schema) -> None:
    """A malformed timestamp is rejected by the schema, not by the library."""
    base = {"weight": 80.0, "systolic": 120, "diastolic": 80, "value_in_ml": 100, "calories": 100}
    data = {k: v for k, v in base.items() if k in {str(key) for key in schema.schema}}
    with pytest.raises(vol.Invalid):
        schema({**data, "timestamp": "yesterday at noon"})
    assert isinstance(schema({**data, "timestamp": "2026-01-24T10:00:00"})["timestamp"], datetime)


def test_body_composition_schema_enforces_ranges() -> None:
    with pytest.raises(vol.Invalid):
        ADD_BODY_COMPOSITION_SCHEMA({"weight": 5})
    with pytest.raises(vol.Invalid):
        ADD_BODY_COMPOSITION_SCHEMA({"weight": 80, "percent_fat": 95})
    assert ADD_BODY_COMPOSITION_SCHEMA({"weight": "80.5"})["weight"] == 80.5


def test_hydration_schema_enforces_library_limit() -> None:
    with pytest.raises(vol.Invalid):
        ADD_HYDRATION_SCHEMA({"value_in_ml": 20000})
    assert ADD_HYDRATION_SCHEMA({"value_in_ml": -150})["value_in_ml"] == -150


def test_create_activity_schema_rejects_negative_distance_and_bad_time_zone() -> None:
    base = {"activity_name": "Run", "activity_type": "running", "duration_min": 10}
    with pytest.raises(vol.Invalid):
        CREATE_ACTIVITY_SCHEMA({**base, "distance_km": -1})
    with pytest.raises(vol.Invalid):
        CREATE_ACTIVITY_SCHEMA({**base, "time_zone": "Mars/Olympus"})
    assert CREATE_ACTIVITY_SCHEMA({**base, "time_zone": "Europe/Berlin"})["time_zone"] == (
        "Europe/Berlin"
    )


def test_workout_schema_accepts_json_string() -> None:
    data = CREATE_WORKOUT_SCHEMA({"workout": '{"workoutName": "Easy"}', "date": "2026-10-16"})
    assert data["workout"] == {"workoutName": "Easy"}
    assert data["date"] == date(2026, 10, 16)


@pytest.mark.parametrize("workout", ["not json", "[1, 2]", [1, 2], 5])
def test_workout_schema_rejects_non_objects(workout: Any) -> None:
    with pytest.raises(vol.Invalid):
        CREATE_WORKOUT_SCHEMA({"workout": workout})


@pytest.mark.parametrize("workout_id", [0, -1, "abc", 1.9, "1.9", True, None, "²", "٤٢"])
def test_workout_ids_reject_values_int_would_change(workout_id: Any) -> None:
    """1.9 or True must not silently become workout 1."""
    with pytest.raises(vol.Invalid):
        DELETE_WORKOUT_SCHEMA({"workout_id": workout_id})


@pytest.mark.parametrize("workout_id", [42, 42.0, "42", " 42 "])
def test_workout_ids_accept_whole_numbers(workout_id: Any) -> None:
    assert DELETE_WORKOUT_SCHEMA({"workout_id": workout_id})["workout_id"] == 42


@pytest.mark.parametrize("schema", [DOWNLOAD_ACTIVITY_SCHEMA, ADD_GEAR_TO_ACTIVITY_SCHEMA])
@pytest.mark.parametrize("activity_id", [1.9, 0, -3, True, "12a"])
def test_activity_id_rejects_values_int_would_change(schema: vol.Schema, activity_id: Any) -> None:
    """activity_id is not truncated (1.9 -> 1) and must be positive."""
    with pytest.raises(vol.Invalid):
        schema({"activity_id": activity_id})


@pytest.mark.parametrize("schema", [DOWNLOAD_ACTIVITY_SCHEMA, ADD_GEAR_TO_ACTIVITY_SCHEMA])
def test_activity_id_accepts_whole_numbers(schema: vol.Schema) -> None:
    """The UI number selector sends 42.0; digit strings come from templates."""
    assert schema({"activity_id": 42.0})["activity_id"] == 42
    assert schema({"activity_id": "42"})["activity_id"] == 42


def test_hydration_selector_matches_schema_range() -> None:
    """The UI selector allows the same range as the schema (±10 L)."""
    services = yaml.safe_load(SERVICES_YAML.read_text())
    number = services["add_hydration"]["fields"]["value_in_ml"]["selector"]["number"]
    assert (number["min"], number["max"]) == (-10000, 10000)
    ADD_HYDRATION_SCHEMA({"value_in_ml": 10000})
    with pytest.raises(vol.Invalid):
        ADD_HYDRATION_SCHEMA({"value_in_ml": 10001})


def test_timestamp_fields_use_datetime_selectors() -> None:
    """Every timestamp field is validated by cv.datetime, so the UI offers a picker."""
    services = yaml.safe_load(SERVICES_YAML.read_text())
    for service in services.values():
        for name, field in (service.get("fields") or {}).items():
            if name in ("timestamp", "start_datetime"):
                assert "datetime" in field["selector"], name

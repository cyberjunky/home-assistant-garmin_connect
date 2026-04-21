"""Tests for Garmin Connect services."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.garmin_connect.const import DOMAIN
from custom_components.garmin_connect.services import (
    async_setup_services,
    async_unload_services,
)


@pytest.fixture
def mock_hass() -> MagicMock:
    """Return a mock Home Assistant instance with a loaded config entry."""
    hass = MagicMock()
    hass.config.time_zone = "Europe/Amsterdam"

    mock_entry = _make_entry("entry_1", "profile_1", "user1@example.com")

    hass.config_entries.async_entries.return_value = [mock_entry]
    return hass


def _make_entry(entry_id: str, unique_id: str, title: str) -> MagicMock:
    """Return a mock config entry with a Garmin client."""
    mock_client = AsyncMock()
    mock_coordinators = MagicMock()
    mock_coordinators.core.client = mock_client

    mock_entry = MagicMock()
    mock_entry.entry_id = entry_id
    mock_entry.unique_id = unique_id
    mock_entry.title = title
    mock_entry.runtime_data = mock_coordinators
    return mock_entry


def _get_handler(mock_hass: MagicMock, service_name: str):
    """Extract a registered service handler by name."""
    for call in mock_hass.services.async_register.call_args_list:
        if call[0][0] == DOMAIN and call[0][1] == service_name:
            return call[0][2]
    raise ValueError(f"Service {service_name} not registered")


def _get_client(mock_hass: MagicMock) -> AsyncMock:
    """Get the mock client from the hass fixture."""
    entry = mock_hass.config_entries.async_entries.return_value[0]
    return entry.runtime_data.core.client


def _get_client_for_entry(mock_hass: MagicMock, entry_id: str) -> AsyncMock:
    """Get the mock client for a specific mock config entry."""
    for entry in mock_hass.config_entries.async_entries.return_value:
        if entry.entry_id == entry_id:
            return entry.runtime_data.core.client
    raise ValueError(f"Entry {entry_id} not configured")


async def test_setup_registers_all_services(mock_hass: MagicMock) -> None:
    """async_setup_services must register all 7 service handlers."""
    await async_setup_services(mock_hass)

    registered = {
        call[0][1] for call in mock_hass.services.async_register.call_args_list
    }
    assert registered == {
        "set_active_gear",
        "add_body_composition",
        "add_blood_pressure",
        "create_activity",
        "upload_activity",
        "add_gear_to_activity",
        "add_hydration",
    }


async def test_unload_removes_all_services(mock_hass: MagicMock) -> None:
    """async_unload_services must remove all 7 services."""
    await async_unload_services(mock_hass)

    removed = {
        call[0][1] for call in mock_hass.services.async_remove.call_args_list
    }
    assert removed == {
        "set_active_gear",
        "add_body_composition",
        "add_blood_pressure",
        "create_activity",
        "upload_activity",
        "add_gear_to_activity",
        "add_hydration",
    }


async def test_service_no_entry_raises(mock_hass: MagicMock) -> None:
    """Services must raise HomeAssistantError when no config entry exists."""
    mock_hass.config_entries.async_entries.return_value = []

    await async_setup_services(mock_hass)
    handler = _get_handler(mock_hass, "add_body_composition")

    call = MagicMock()
    call.data = {"weight": 80.0}

    with pytest.raises(HomeAssistantError):
        await handler(call)


async def test_service_entry_not_loaded_raises(mock_hass: MagicMock) -> None:
    """Services must raise HomeAssistantError when entry has no runtime_data."""
    mock_entry = MagicMock()
    mock_entry.runtime_data = None
    mock_hass.config_entries.async_entries.return_value = [mock_entry]

    await async_setup_services(mock_hass)
    handler = _get_handler(mock_hass, "add_body_composition")

    call = MagicMock()
    call.data = {"weight": 80.0}

    with pytest.raises(HomeAssistantError):
        await handler(call)


async def test_set_active_gear_by_uuid(mock_hass: MagicMock) -> None:
    """set_active_gear must call client with the supplied gear_uuid."""
    await async_setup_services(mock_hass)
    handler = _get_handler(mock_hass, "set_active_gear")
    client = _get_client(mock_hass)

    call = MagicMock()
    call.data = {
        "gear_uuid": "abc-123",
        "activity_type": "running",
        "setting": "set as default",
    }

    await handler(call)

    client.set_active_gear.assert_awaited_once_with(
        activity_type="running",
        setting="set as default",
        gear_uuid="abc-123",
    )


async def test_set_active_gear_by_entity_id(mock_hass: MagicMock) -> None:
    """set_active_gear must resolve gear_uuid from entity state attributes."""
    await async_setup_services(mock_hass)
    handler = _get_handler(mock_hass, "set_active_gear")

    state = MagicMock()
    state.attributes = {"gear_uuid": "resolved-uuid"}
    mock_hass.states.get.return_value = state

    call = MagicMock()
    call.data = {
        "entity_id": "sensor.garmin_my_shoes",
        "activity_type": "running",
        "setting": "set as default",
    }

    registry_entry = MagicMock()
    registry_entry.config_entry_id = "entry_1"

    with patch("custom_components.garmin_connect.services.er.async_get") as async_get:
        async_get.return_value.async_get.return_value = registry_entry
        await handler(call)

    client = _get_client(mock_hass)
    client.set_active_gear.assert_awaited_once_with(
        activity_type="running",
        setting="set as default",
        gear_uuid="resolved-uuid",
    )


async def test_set_active_gear_by_entity_id_targets_entity_account(
    mock_hass: MagicMock,
):
    """set_active_gear must use the account that owns the gear entity."""
    second_entry = _make_entry("entry_2", "profile_2", "user2@example.com")
    mock_hass.config_entries.async_entries.return_value.append(second_entry)

    state = MagicMock()
    state.attributes = {"gear_uuid": "resolved-uuid"}
    mock_hass.states.get.return_value = state

    registry_entry = MagicMock()
    registry_entry.config_entry_id = "entry_2"

    await async_setup_services(mock_hass)
    handler = _get_handler(mock_hass, "set_active_gear")
    first_client = _get_client_for_entry(mock_hass, "entry_1")
    second_client = _get_client_for_entry(mock_hass, "entry_2")

    call = MagicMock()
    call.data = {
        "entity_id": "sensor.second_garmin_shoes",
        "activity_type": "running",
        "setting": "set as default",
    }

    with patch("custom_components.garmin_connect.services.er.async_get") as async_get:
        async_get.return_value.async_get.return_value = registry_entry
        await handler(call)

    first_client.set_active_gear.assert_not_awaited()
    second_client.set_active_gear.assert_awaited_once_with(
        activity_type="running",
        setting="set as default",
        gear_uuid="resolved-uuid",
    )


async def test_set_active_gear_no_gear_raises(mock_hass: MagicMock) -> None:
    """set_active_gear must raise when neither uuid nor entity_id given."""
    await async_setup_services(mock_hass)
    handler = _get_handler(mock_hass, "set_active_gear")

    call = MagicMock()
    call.data = {"activity_type": "running", "setting": "set as default"}

    with pytest.raises(HomeAssistantError):
        await handler(call)


async def test_set_active_gear_entity_not_found_raises(mock_hass: MagicMock) -> None:
    """set_active_gear must raise when entity doesn't exist."""
    await async_setup_services(mock_hass)
    handler = _get_handler(mock_hass, "set_active_gear")

    mock_hass.states.get.return_value = None

    call = MagicMock()
    call.data = {
        "entity_id": "sensor.garmin_nonexistent",
        "activity_type": "running",
        "setting": "set as default",
    }

    with pytest.raises(HomeAssistantError):
        await handler(call)


async def test_set_active_gear_entity_no_uuid_raises(mock_hass: MagicMock) -> None:
    """set_active_gear must raise when entity has no gear_uuid attribute."""
    await async_setup_services(mock_hass)
    handler = _get_handler(mock_hass, "set_active_gear")

    state = MagicMock()
    state.attributes = {}
    mock_hass.states.get.return_value = state

    call = MagicMock()
    call.data = {
        "entity_id": "sensor.garmin_some_sensor",
        "activity_type": "running",
        "setting": "set as default",
    }

    with pytest.raises(HomeAssistantError):
        await handler(call)


async def test_add_body_composition(mock_hass: MagicMock) -> None:
    """add_body_composition must call client with the supplied fields."""
    await async_setup_services(mock_hass)
    handler = _get_handler(mock_hass, "add_body_composition")
    client = _get_client(mock_hass)

    call = MagicMock()
    call.data = {
        "weight": 80.5,
        "percent_fat": 15.0,
        "muscle_mass": 35.0,
    }

    await handler(call)

    client.add_body_composition.assert_awaited_once()
    kwargs = client.add_body_composition.call_args.kwargs
    assert kwargs["weight"] == 80.5
    assert kwargs["percent_fat"] == 15.0
    assert kwargs["muscle_mass"] == 35.0


async def test_add_body_composition_targets_entity_config_entry(
    mock_hass: MagicMock,
):
    """add_body_composition must target the account that owns entity_id."""
    second_entry = _make_entry("entry_2", "profile_2", "user2@example.com")
    mock_hass.config_entries.async_entries.return_value.append(second_entry)

    registry_entry = MagicMock()
    registry_entry.config_entry_id = "entry_2"

    await async_setup_services(mock_hass)
    handler = _get_handler(mock_hass, "add_body_composition")
    first_client = _get_client_for_entry(mock_hass, "entry_1")
    second_client = _get_client_for_entry(mock_hass, "entry_2")

    call = MagicMock()
    call.data = {
        "entity_id": "sensor.second_garmin_weight",
        "weight": 72.0,
    }

    with patch("custom_components.garmin_connect.services.er.async_get") as async_get:
        async_get.return_value.async_get.return_value = registry_entry
        await handler(call)

    first_client.add_body_composition.assert_not_awaited()
    second_client.add_body_composition.assert_awaited_once()
    assert second_client.add_body_composition.call_args.kwargs["weight"] == 72.0


async def test_add_body_composition_entity_not_found_raises(
    mock_hass: MagicMock,
):
    """add_body_composition must raise when the requested entity is unknown."""
    await async_setup_services(mock_hass)
    handler = _get_handler(mock_hass, "add_body_composition")

    call = MagicMock()
    call.data = {"entity_id": "sensor.missing_weight", "weight": 80.0}

    with patch("custom_components.garmin_connect.services.er.async_get") as async_get:
        async_get.return_value.async_get.return_value = None
        with pytest.raises(HomeAssistantError):
            await handler(call)


async def test_add_body_composition_api_error_raises(mock_hass: MagicMock) -> None:
    """add_body_composition must wrap API errors in HomeAssistantError."""
    await async_setup_services(mock_hass)
    handler = _get_handler(mock_hass, "add_body_composition")
    client = _get_client(mock_hass)
    client.add_body_composition.side_effect = Exception("API error")

    call = MagicMock()
    call.data = {"weight": 80.0}

    with pytest.raises(HomeAssistantError):
        await handler(call)


async def test_add_blood_pressure(mock_hass: MagicMock) -> None:
    """add_blood_pressure must call client.set_blood_pressure with correct args."""
    await async_setup_services(mock_hass)
    handler = _get_handler(mock_hass, "add_blood_pressure")
    client = _get_client(mock_hass)

    call = MagicMock()
    call.data = {
        "systolic": 120,
        "diastolic": 80,
        "pulse": 70,
        "notes": "Morning reading",
    }

    await handler(call)

    client.set_blood_pressure.assert_awaited_once_with(
        systolic=120,
        diastolic=80,
        pulse=70,
        timestamp=None,
        notes="Morning reading",
    )


async def test_add_blood_pressure_wraps_exception(mock_hass: MagicMock) -> None:
    """add_blood_pressure must wrap API errors in HomeAssistantError."""
    await async_setup_services(mock_hass)
    handler = _get_handler(mock_hass, "add_blood_pressure")
    client = _get_client(mock_hass)
    client.set_blood_pressure.side_effect = RuntimeError("network error")

    call = MagicMock()
    call.data = {"systolic": 120, "diastolic": 80, "pulse": 70}

    with pytest.raises(HomeAssistantError):
        await handler(call)


async def test_create_activity(mock_hass: MagicMock) -> None:
    """create_activity must forward all fields and append .000 to start_datetime."""
    await async_setup_services(mock_hass)
    handler = _get_handler(mock_hass, "create_activity")
    client = _get_client(mock_hass)

    call = MagicMock()
    call.data = {
        "activity_name": "Morning Run",
        "activity_type": "running",
        "start_datetime": "2026-01-24T08:00:00",
        "duration_min": 30,
        "distance_km": 5.0,
    }

    await handler(call)

    client.create_activity.assert_awaited_once()
    kwargs = client.create_activity.call_args.kwargs
    assert kwargs["activity_name"] == "Morning Run"
    assert kwargs["activity_type"] == "running"
    assert kwargs["duration_min"] == 30
    assert kwargs["distance_km"] == 5.0
    assert kwargs["time_zone"] == "Europe/Amsterdam"
    assert kwargs["start_datetime"] == "2026-01-24T08:00:00.000"


async def test_create_activity_defaults_to_now(mock_hass: MagicMock) -> None:
    """create_activity must generate a start_datetime when not supplied."""
    await async_setup_services(mock_hass)
    handler = _get_handler(mock_hass, "create_activity")
    client = _get_client(mock_hass)

    call = MagicMock()
    call.data = {
        "activity_name": "Walk",
        "activity_type": "walking",
        "duration_min": 15,
    }

    await handler(call)

    kwargs = client.create_activity.call_args.kwargs
    assert kwargs["start_datetime"] is not None
    assert ".000" in kwargs["start_datetime"]


async def test_upload_activity(mock_hass: MagicMock, tmp_path: Path) -> None:
    """upload_activity must call client.upload_activity when the file exists."""
    await async_setup_services(mock_hass)
    handler = _get_handler(mock_hass, "upload_activity")
    client = _get_client(mock_hass)

    fit_file = tmp_path / "activity.fit"
    fit_file.write_bytes(b"fake fit data")

    call = MagicMock()
    call.data = {"file_path": str(fit_file)}

    await handler(call)

    client.upload_activity.assert_awaited_once_with(str(fit_file))


async def test_upload_activity_file_not_found_raises(mock_hass: MagicMock) -> None:
    """upload_activity must raise HomeAssistantError when file doesn't exist."""
    await async_setup_services(mock_hass)
    handler = _get_handler(mock_hass, "upload_activity")

    call = MagicMock()
    call.data = {"file_path": "/nonexistent/activity.fit"}

    with pytest.raises(HomeAssistantError):
        await handler(call)


async def test_add_gear_to_activity_by_uuid(mock_hass: MagicMock) -> None:
    """add_gear_to_activity must call client with gear_uuid and activity_id."""
    await async_setup_services(mock_hass)
    handler = _get_handler(mock_hass, "add_gear_to_activity")
    client = _get_client(mock_hass)

    call = MagicMock()
    call.data = {"activity_id": 12345, "gear_uuid": "gear-abc"}

    await handler(call)

    client.add_gear_to_activity.assert_awaited_once_with(
        gear_uuid="gear-abc",
        activity_id=12345,
    )


async def test_add_gear_to_activity_by_entity(mock_hass: MagicMock) -> None:
    """add_gear_to_activity must resolve uuid from entity state attributes."""
    await async_setup_services(mock_hass)
    handler = _get_handler(mock_hass, "add_gear_to_activity")
    client = _get_client(mock_hass)

    state = MagicMock()
    state.attributes = {"gear_uuid": "entity-uuid"}
    mock_hass.states.get.return_value = state

    call = MagicMock()
    call.data = {"activity_id": 99999, "entity_id": "sensor.garmin_shoes"}

    registry_entry = MagicMock()
    registry_entry.config_entry_id = "entry_1"

    with patch("custom_components.garmin_connect.services.er.async_get") as async_get:
        async_get.return_value.async_get.return_value = registry_entry
        await handler(call)

    client.add_gear_to_activity.assert_awaited_once_with(
        gear_uuid="entity-uuid",
        activity_id=99999,
    )


async def test_add_gear_to_activity_no_gear_raises(mock_hass: MagicMock) -> None:
    """add_gear_to_activity must raise when no gear is specified."""
    await async_setup_services(mock_hass)
    handler = _get_handler(mock_hass, "add_gear_to_activity")

    call = MagicMock()
    call.data = {"activity_id": 99999}

    with pytest.raises(HomeAssistantError):
        await handler(call)


async def test_add_hydration(mock_hass: MagicMock) -> None:
    """add_hydration must call client.set_hydration with value_in_ml."""
    await async_setup_services(mock_hass)
    handler = _get_handler(mock_hass, "add_hydration")
    client = _get_client(mock_hass)

    call = MagicMock()
    call.data = {"value_in_ml": 250.0}

    await handler(call)

    client.set_hydration.assert_awaited_once_with(
        value_in_ml=250.0,
        timestamp=None,
    )


async def test_add_hydration_with_timestamp(mock_hass: MagicMock) -> None:
    """add_hydration must forward an optional timestamp to the client."""
    await async_setup_services(mock_hass)
    handler = _get_handler(mock_hass, "add_hydration")
    client = _get_client(mock_hass)

    call = MagicMock()
    call.data = {"value_in_ml": 500.0, "timestamp": "2026-01-24T10:00:00"}

    await handler(call)

    client.set_hydration.assert_awaited_once_with(
        value_in_ml=500.0,
        timestamp="2026-01-24T10:00:00",
    )


async def test_add_hydration_negative_value(mock_hass: MagicMock) -> None:
    """add_hydration must accept negative values to subtract intake."""
    await async_setup_services(mock_hass)
    handler = _get_handler(mock_hass, "add_hydration")
    client = _get_client(mock_hass)

    call = MagicMock()
    call.data = {"value_in_ml": -150.0}

    await handler(call)

    client.set_hydration.assert_awaited_once_with(
        value_in_ml=-150.0,
        timestamp=None,
    )


async def test_add_hydration_wraps_exception(mock_hass: MagicMock) -> None:
    """add_hydration must wrap API errors in HomeAssistantError."""
    await async_setup_services(mock_hass)
    handler = _get_handler(mock_hass, "add_hydration")
    client = _get_client(mock_hass)
    client.set_hydration.side_effect = RuntimeError("API error")

    call = MagicMock()
    call.data = {"value_in_ml": 250.0}

    with pytest.raises(HomeAssistantError):
        await handler(call)
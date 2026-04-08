"""Tests for Garmin Connect integration setup and migration."""

from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.garmin_connect import (
    _migrate_entity_unique_ids,
    async_migrate_entry,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.garmin_connect.const import (
    CONF_CLIENT_ID,
    CONF_REFRESH_TOKEN,
    CONF_TOKEN,
)

from .conftest import ENTRY_DATA

_COORD_TARGETS = [
    "custom_components.garmin_connect.CoreCoordinator",
    "custom_components.garmin_connect.ActivityCoordinator",
    "custom_components.garmin_connect.TrainingCoordinator",
    "custom_components.garmin_connect.BodyCoordinator",
    "custom_components.garmin_connect.GoalsCoordinator",
    "custom_components.garmin_connect.GearCoordinator",
    "custom_components.garmin_connect.BloodPressureCoordinator",
    "custom_components.garmin_connect.MenstrualCoordinator",
]


def _coord_mock() -> MagicMock:
    """Return a coordinator mock with async_config_entry_first_refresh stubbed."""
    c = MagicMock()
    c.async_config_entry_first_refresh = AsyncMock()
    c.data = {}
    return c


def _stack_coordinators(stack: ExitStack, coord: MagicMock) -> None:
    """Push patches for all 8 coordinator constructors onto an ExitStack."""
    for target in _COORD_TARGETS:
        stack.enter_context(patch(target, return_value=coord))


# ── Setup tests ───────────────────────────────────────────────────────────────


async def test_setup_entry_success() -> None:
    """Test that a config entry sets up correctly and returns True."""
    entry = MagicMock()
    entry.data = dict(ENTRY_DATA)
    entry.options = {}
    hass = MagicMock()
    hass.config.country = "US"
    hass.services.has_service = MagicMock(return_value=False)

    coord = _coord_mock()
    with ExitStack() as stack:
        stack.enter_context(
            patch("custom_components.garmin_connect.GarminAuth", return_value=MagicMock())
        )
        stack.enter_context(patch("custom_components.garmin_connect.GarminClient"))
        _stack_coordinators(stack, coord)
        stack.enter_context(
            patch(
                "custom_components.garmin_connect.async_setup_services",
                new=AsyncMock(),
            )
        )
        hass.config_entries.async_forward_entry_setups = AsyncMock()
        result = await async_setup_entry(hass, entry)

    assert result is True
    assert entry.runtime_data is not None


async def test_setup_entry_stores_all_coordinators() -> None:
    """runtime_data must be a GarminConnectCoordinators with all 8 fields."""
    from custom_components.garmin_connect.coordinator import GarminConnectCoordinators

    entry = MagicMock()
    entry.data = dict(ENTRY_DATA)
    entry.options = {}
    hass = MagicMock()
    hass.config.country = "US"
    hass.services.has_service = MagicMock(return_value=True)

    coord = _coord_mock()
    with ExitStack() as stack:
        stack.enter_context(patch("custom_components.garmin_connect.GarminAuth"))
        stack.enter_context(patch("custom_components.garmin_connect.GarminClient"))
        _stack_coordinators(stack, coord)
        hass.config_entries.async_forward_entry_setups = AsyncMock()
        await async_setup_entry(hass, entry)

    assert isinstance(entry.runtime_data, GarminConnectCoordinators)
    for field in (
        "core", "activity", "training", "body", "goals", "gear",
        "blood_pressure", "menstrual",
    ):
        assert getattr(entry.runtime_data, field) is coord


async def test_setup_entry_restores_di_tokens_onto_auth() -> None:
    """Tokens from config entry data must be assigned to auth before client is built."""
    entry = MagicMock()
    entry.data = dict(ENTRY_DATA)
    entry.options = {}
    hass = MagicMock()
    hass.config.country = "US"
    hass.services.has_service = MagicMock(return_value=True)

    captured: dict = {}

    def _capture_auth(is_cn=False):
        auth = MagicMock()
        captured["auth"] = auth
        return auth

    coord = _coord_mock()
    with ExitStack() as stack:
        stack.enter_context(
            patch(
                "custom_components.garmin_connect.GarminAuth",
                side_effect=_capture_auth,
            )
        )
        stack.enter_context(patch("custom_components.garmin_connect.GarminClient"))
        _stack_coordinators(stack, coord)
        hass.config_entries.async_forward_entry_setups = AsyncMock()
        await async_setup_entry(hass, entry)

    auth = captured["auth"]
    assert auth.di_token == ENTRY_DATA[CONF_TOKEN]
    assert auth.di_refresh_token == ENTRY_DATA[CONF_REFRESH_TOKEN]
    assert auth.di_client_id == ENTRY_DATA[CONF_CLIENT_ID]


async def test_setup_entry_registers_services_when_not_present() -> None:
    """Services are registered when has_service returns False."""
    entry = MagicMock()
    entry.data = dict(ENTRY_DATA)
    entry.options = {}
    hass = MagicMock()
    hass.config.country = "US"
    hass.services.has_service = MagicMock(return_value=False)

    coord = _coord_mock()
    setup_services = AsyncMock()
    with ExitStack() as stack:
        stack.enter_context(patch("custom_components.garmin_connect.GarminAuth"))
        stack.enter_context(patch("custom_components.garmin_connect.GarminClient"))
        _stack_coordinators(stack, coord)
        stack.enter_context(
            patch(
                "custom_components.garmin_connect.async_setup_services",
                setup_services,
            )
        )
        hass.config_entries.async_forward_entry_setups = AsyncMock()
        await async_setup_entry(hass, entry)

    setup_services.assert_awaited_once()


async def test_setup_entry_skips_services_when_already_registered() -> None:
    """Services are not re-registered when has_service returns True."""
    entry = MagicMock()
    entry.data = dict(ENTRY_DATA)
    entry.options = {}
    hass = MagicMock()
    hass.config.country = "US"
    hass.services.has_service = MagicMock(return_value=True)

    coord = _coord_mock()
    setup_services = AsyncMock()
    with ExitStack() as stack:
        stack.enter_context(patch("custom_components.garmin_connect.GarminAuth"))
        stack.enter_context(patch("custom_components.garmin_connect.GarminClient"))
        _stack_coordinators(stack, coord)
        stack.enter_context(
            patch(
                "custom_components.garmin_connect.async_setup_services",
                setup_services,
            )
        )
        hass.config_entries.async_forward_entry_setups = AsyncMock()
        await async_setup_entry(hass, entry)

    setup_services.assert_not_awaited()


# ── Unload tests ──────────────────────────────────────────────────────────────


async def test_unload_entry_unregisters_services_when_last_entry() -> None:
    """Services are removed when the last config entry is unloaded."""
    entry = MagicMock()
    hass = MagicMock()
    hass.config_entries.async_entries = MagicMock(return_value=[entry])
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

    unload_services = AsyncMock()
    with patch(
        "custom_components.garmin_connect.async_unload_services", unload_services
    ):
        result = await async_unload_entry(hass, entry)

    assert result is True
    unload_services.assert_awaited_once()


async def test_unload_entry_keeps_services_when_other_entries_exist() -> None:
    """Services are NOT removed when other config entries remain loaded."""
    entry1, entry2 = MagicMock(), MagicMock()
    hass = MagicMock()
    hass.config_entries.async_entries = MagicMock(return_value=[entry1, entry2])
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

    unload_services = AsyncMock()
    with patch(
        "custom_components.garmin_connect.async_unload_services", unload_services
    ):
        result = await async_unload_entry(hass, entry1)

    assert result is True
    unload_services.assert_not_awaited()


# ── Migration tests ───────────────────────────────────────────────────────────


async def test_migrate_v1_to_v2_bumps_version_and_triggers_reauth() -> None:
    """V1 entries must be bumped to v2 and reauth triggered."""
    mock_entry = MagicMock()
    mock_entry.version = 1
    mock_entry.unique_id = "user@example.com"
    mock_entry.entry_id = "test_entry_id"
    mock_entry.title = "user@example.com"
    mock_hass = MagicMock()

    with (
        patch("custom_components.garmin_connect.er.async_get"),
        patch(
            "custom_components.garmin_connect.er.async_entries_for_config_entry",
            return_value=[],
        ),
    ):
        result = await async_migrate_entry(mock_hass, mock_entry)

    assert result is True
    mock_hass.config_entries.async_update_entry.assert_called_once_with(
        mock_entry, version=2
    )
    mock_entry.async_start_reauth.assert_called_once_with(mock_hass)


async def test_migrate_v2_is_noop() -> None:
    """V2 entries must not be migrated again."""
    mock_entry = MagicMock()
    mock_entry.version = 2
    mock_hass = MagicMock()

    result = await async_migrate_entry(mock_hass, mock_entry)

    assert result is True
    mock_hass.config_entries.async_update_entry.assert_not_called()


async def test_migrate_entity_unique_ids_unchanged_key() -> None:
    """Entities with unchanged keys get prefix migrated (email -> entry_id)."""
    mock_hass = MagicMock()
    mock_entry = MagicMock()
    mock_entry.entry_id = "new_entry_id"

    mock_entity = MagicMock()
    mock_entity.unique_id = "user@example.com_totalSteps"
    mock_entity.entity_id = "sensor.total_steps"

    mock_registry = MagicMock()

    with (
        patch("custom_components.garmin_connect.er.async_get", return_value=mock_registry),
        patch(
            "custom_components.garmin_connect.er.async_entries_for_config_entry",
            return_value=[mock_entity],
        ),
    ):
        _migrate_entity_unique_ids(mock_hass, mock_entry, "user@example.com")

    mock_registry.async_update_entity.assert_called_once_with(
        "sensor.total_steps",
        new_unique_id="new_entry_id_totalSteps",
    )


async def test_migrate_entity_unique_ids_renamed_key() -> None:
    """Entities with renamed keys get both prefix and key migrated."""
    mock_hass = MagicMock()
    mock_entry = MagicMock()
    mock_entry.entry_id = "new_entry_id"

    mock_entity = MagicMock()
    mock_entity.unique_id = "user@example.com_sleepingSeconds"
    mock_entity.entity_id = "sensor.sleeping_time"

    mock_registry = MagicMock()

    with (
        patch("custom_components.garmin_connect.er.async_get", return_value=mock_registry),
        patch(
            "custom_components.garmin_connect.er.async_entries_for_config_entry",
            return_value=[mock_entity],
        ),
    ):
        _migrate_entity_unique_ids(mock_hass, mock_entry, "user@example.com")

    mock_registry.async_update_entity.assert_called_once_with(
        "sensor.sleeping_time",
        new_unique_id="new_entry_id_sleepingMinutes",
    )


async def test_migrate_entity_unique_ids_dropped_key_skipped() -> None:
    """Dropped sensors (mapped to None) must be skipped during migration."""
    mock_hass = MagicMock()
    mock_entry = MagicMock()
    mock_entry.entry_id = "new_entry_id"

    mock_entity = MagicMock()
    mock_entity.unique_id = "user@example.com_netCalorieGoal"
    mock_entity.entity_id = "sensor.net_calorie_goal"

    mock_registry = MagicMock()

    with (
        patch("custom_components.garmin_connect.er.async_get", return_value=mock_registry),
        patch(
            "custom_components.garmin_connect.er.async_entries_for_config_entry",
            return_value=[mock_entity],
        ),
    ):
        _migrate_entity_unique_ids(mock_hass, mock_entry, "user@example.com")

    mock_registry.async_update_entity.assert_not_called()


async def test_migrate_entity_unique_ids_conflict_handled() -> None:
    """Unique_id conflicts must be logged but not fail migration."""
    mock_hass = MagicMock()
    mock_entry = MagicMock()
    mock_entry.entry_id = "new_entry_id"

    mock_entity = MagicMock()
    mock_entity.unique_id = "user@example.com_totalSteps"
    mock_entity.entity_id = "sensor.total_steps"

    mock_registry = MagicMock()
    mock_registry.async_update_entity.side_effect = ValueError("conflict")

    with (
        patch("custom_components.garmin_connect.er.async_get", return_value=mock_registry),
        patch(
            "custom_components.garmin_connect.er.async_entries_for_config_entry",
            return_value=[mock_entity],
        ),
    ):
        _migrate_entity_unique_ids(mock_hass, mock_entry, "user@example.com")

    mock_registry.async_update_entity.assert_called_once()


async def test_migrate_entity_non_matching_prefix_skipped() -> None:
    """Entities not matching the old prefix must be skipped."""
    mock_hass = MagicMock()
    mock_entry = MagicMock()
    mock_entry.entry_id = "new_entry_id"

    mock_entity = MagicMock()
    mock_entity.unique_id = "other_prefix_totalSteps"
    mock_entity.entity_id = "sensor.total_steps"

    mock_registry = MagicMock()

    with (
        patch("custom_components.garmin_connect.er.async_get", return_value=mock_registry),
        patch(
            "custom_components.garmin_connect.er.async_entries_for_config_entry",
            return_value=[mock_entity],
        ),
    ):
        _migrate_entity_unique_ids(mock_hass, mock_entry, "user@example.com")

    mock_registry.async_update_entity.assert_not_called()

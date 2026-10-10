"""Tests for Garmin Connect integration setup and migration."""

import asyncio
from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.exceptions import ConfigEntryAuthFailed

from custom_components.garmin_connect import (
    _migrate_entity_unique_ids,
    async_migrate_entry,
    async_options_update_listener,
    async_setup,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.garmin_connect.const import (
    CONF_CLIENT_ID,
    CONF_IS_CN,
    CONF_REFRESH_TOKEN,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
)
from custom_components.garmin_connect.coordinator import GarminConnectCoordinators

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
    "custom_components.garmin_connect.NutritionCoordinator",
]


def _coord_mock() -> MagicMock:
    """Return a coordinator mock with async methods stubbed."""
    c = MagicMock()
    c.async_config_entry_first_refresh = AsyncMock()
    c.async_refresh = AsyncMock()
    c.data = {}
    return c


def _stack_coordinators(stack: ExitStack, coord: MagicMock) -> None:
    """Push patches for all 9 coordinator constructors onto an ExitStack."""
    for target in _COORD_TARGETS:
        stack.enter_context(patch(target, return_value=coord))


# ── Setup tests ───────────────────────────────────────────────────────────────


async def test_setup_entry_requires_token() -> None:
    """Missing token must raise ConfigEntryAuthFailed."""
    entry = MagicMock()
    entry.data = {}
    entry.title = "test@example.com"
    hass = MagicMock()

    with pytest.raises(ConfigEntryAuthFailed):
        await async_setup_entry(hass, entry)


async def test_setup_entry_success() -> None:
    """Test that a config entry sets up correctly and returns True."""
    entry = MagicMock()
    entry.data = dict(ENTRY_DATA)
    entry.options = {}
    hass = MagicMock()
    hass.config.country = "US"

    coord = _coord_mock()
    with ExitStack() as stack:
        stack.enter_context(
            patch("custom_components.garmin_connect.GarminAuth", return_value=MagicMock())
        )
        stack.enter_context(patch("custom_components.garmin_connect.GarminClient"))
        _stack_coordinators(stack, coord)
        hass.config_entries.async_forward_entry_setups = AsyncMock()
        result = await async_setup_entry(hass, entry)

    assert result is True
    assert entry.runtime_data is not None


async def test_setup_entry_stores_all_coordinators() -> None:
    """runtime_data must be a GarminConnectCoordinators with all 9 fields."""
    entry = MagicMock()
    entry.data = dict(ENTRY_DATA)
    entry.options = {}
    hass = MagicMock()
    hass.config.country = "US"

    coord = _coord_mock()
    with ExitStack() as stack:
        stack.enter_context(patch("custom_components.garmin_connect.GarminAuth"))
        stack.enter_context(patch("custom_components.garmin_connect.GarminClient"))
        _stack_coordinators(stack, coord)
        hass.config_entries.async_forward_entry_setups = AsyncMock()
        await async_setup_entry(hass, entry)

    assert isinstance(entry.runtime_data, GarminConnectCoordinators)
    for field in (
        "core",
        "activity",
        "training",
        "body",
        "goals",
        "gear",
        "blood_pressure",
        "menstrual",
        "nutrition",
    ):
        assert getattr(entry.runtime_data, field) is coord


async def test_setup_entry_restores_di_tokens_onto_auth() -> None:
    """Tokens from config entry data must be assigned to auth before client is built."""
    entry = MagicMock()
    entry.data = dict(ENTRY_DATA)
    entry.options = {}
    hass = MagicMock()
    hass.config.country = "US"

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


async def test_setup_entry_records_region_for_reload_detection() -> None:
    """The China-region flag the client was built with is kept on runtime_data."""
    entry = MagicMock()
    entry.data = dict(ENTRY_DATA)
    entry.options = {CONF_IS_CN: True}
    hass = MagicMock()

    coord = _coord_mock()
    with ExitStack() as stack:
        stack.enter_context(patch("custom_components.garmin_connect.GarminAuth"))
        stack.enter_context(patch("custom_components.garmin_connect.GarminClient"))
        _stack_coordinators(stack, coord)
        hass.config_entries.async_forward_entry_setups = AsyncMock()
        await async_setup_entry(hass, entry)

    assert entry.runtime_data.is_cn is True


async def test_setup_entry_core_failure_propagates() -> None:
    """A failing core refresh (ConfigEntryNotReady/AuthFailed) must surface, not be swallowed."""
    from homeassistant.exceptions import ConfigEntryNotReady

    entry = MagicMock()
    entry.data = dict(ENTRY_DATA)
    entry.options = {}
    hass = MagicMock()

    coord = _coord_mock()
    coord.async_config_entry_first_refresh = AsyncMock(side_effect=ConfigEntryNotReady("down"))
    with ExitStack() as stack:
        stack.enter_context(patch("custom_components.garmin_connect.GarminAuth"))
        stack.enter_context(patch("custom_components.garmin_connect.GarminClient"))
        _stack_coordinators(stack, coord)
        with pytest.raises(ConfigEntryNotReady):
            await async_setup_entry(hass, entry)


async def test_stalled_core_setup_retries_without_starting_optional_tasks(
    hass, mock_config_entry, mock_auth, mock_client
) -> None:
    """A stalled first refresh must fail promptly and cancel the awaited work."""
    from homeassistant.exceptions import ConfigEntryNotReady

    cancelled = asyncio.Event()

    async def stalled_refresh():
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    coord = _coord_mock()
    coord.async_config_entry_first_refresh.side_effect = stalled_refresh
    with ExitStack() as stack:
        _stack_coordinators(stack, coord)
        stack.enter_context(patch("custom_components.garmin_connect.CORE_SETUP_TIMEOUT", 0.01))
        forward = stack.enter_context(
            patch.object(hass.config_entries, "async_forward_entry_setups", new=AsyncMock())
        )
        with pytest.raises(ConfigEntryNotReady, match="core initialization exceeded"):
            await asyncio.wait_for(async_setup_entry(hass, mock_config_entry), timeout=1)

    assert cancelled.is_set()
    forward.assert_not_awaited()
    assert not mock_config_entry._background_tasks


async def test_optional_refresh_does_not_block_startup_and_is_cancelled_on_unload(
    hass, mock_config_entry, mock_auth, mock_client
) -> None:
    """HA startup completes while optional work is pending; unload cancels it."""
    started = asyncio.Event()
    cancelled = asyncio.Event()
    optional = _coord_mock()
    optional.data_name = "training"

    async def stalled_refresh():
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    optional.async_refresh.side_effect = stalled_refresh
    core = _coord_mock()
    with ExitStack() as stack:
        _stack_coordinators(stack, core)
        stack.enter_context(
            patch("custom_components.garmin_connect.TrainingCoordinator", return_value=optional)
        )

        async def forward_platforms(*args):
            # Optional data must be unavailable and its refresh must not race
            # the entity listeners installed by platform setup.
            assert optional.last_update_success is False
            optional.async_refresh.assert_not_awaited()

        stack.enter_context(
            patch.object(
                hass.config_entries,
                "async_forward_entry_setups",
                new=AsyncMock(side_effect=forward_platforms),
            )
        )
        assert await asyncio.wait_for(async_setup_entry(hass, mock_config_entry), timeout=1)
        await asyncio.wait_for(started.wait(), timeout=1)
        # HA's startup barrier deliberately excludes entry background tasks.
        await asyncio.wait_for(hass.async_block_till_done(), timeout=1)
        assert mock_config_entry._background_tasks
        await mock_config_entry._async_process_on_unload(hass)

    assert cancelled.is_set()
    assert not mock_config_entry._background_tasks


# ── Options listener ──────────────────────────────────────────────────────────


def _coordinators(is_cn: bool = False) -> GarminConnectCoordinators:
    coords = [MagicMock() for _ in range(9)]
    return GarminConnectCoordinators(*coords, is_cn=is_cn)


async def test_options_listener_updates_intervals() -> None:
    """A new scan interval is pushed to every coordinator without a reload."""
    hass = MagicMock()
    hass.config_entries.async_reload = AsyncMock()
    entry = MagicMock()
    entry.options = {CONF_SCAN_INTERVAL: 120}
    entry.runtime_data = _coordinators()

    await async_options_update_listener(hass, entry)

    hass.config_entries.async_reload.assert_not_awaited()
    for coord in entry.runtime_data:
        coord.set_update_interval.assert_called_once()
        (interval,) = coord.set_update_interval.call_args.args
        assert interval.total_seconds() == 120


async def test_options_listener_reloads_when_region_changes() -> None:
    """Switching the China region needs a new client, so the entry is reloaded."""
    hass = MagicMock()
    hass.config_entries.async_reload = AsyncMock()
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.options = {CONF_IS_CN: True}
    entry.runtime_data = _coordinators(is_cn=False)

    await async_options_update_listener(hass, entry)

    hass.config_entries.async_reload.assert_awaited_once_with("test_entry_id")
    for coord in entry.runtime_data:
        coord.set_update_interval.assert_not_called()


# ── Unload tests ──────────────────────────────────────────────────────────────


async def test_unload_entry_unloads_platforms() -> None:
    """Unloading only tears down platforms; services stay registered for other entries."""
    entry = MagicMock()
    hass = MagicMock()
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

    assert await async_unload_entry(hass, entry) is True
    hass.services.async_remove.assert_not_called()


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
    mock_hass.config_entries.async_update_entry.assert_called_once_with(mock_entry, version=2)
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


async def test_async_setup_serves_and_registers_route_card() -> None:
    """The card folder is served once and the card auto-loaded, version-busted."""
    hass = MagicMock()
    hass.http.async_register_static_paths = AsyncMock()
    integration = MagicMock()
    integration.version = "9.9.9"

    with (
        patch(
            "custom_components.garmin_connect.async_get_integration",
            AsyncMock(return_value=integration),
        ),
        patch("custom_components.garmin_connect.add_extra_js_url") as add_js,
        patch("custom_components.garmin_connect.async_setup_services") as setup_services,
    ):
        assert await async_setup(hass, {}) is True

    setup_services.assert_called_once_with(hass)

    (configs,) = hass.http.async_register_static_paths.await_args.args
    assert len(configs) == 1
    assert configs[0].url_path == "/garmin_connect"
    assert configs[0].path.endswith("custom_components/garmin_connect/www")
    add_js.assert_called_once_with(hass, "/garmin_connect/garmin-polyline-card.js?v=9.9.9")

"""Tests for Garmin Connect integration setup and migration."""

from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.garmin_connect import (
    _migrate_entity_unique_ids,
    async_migrate_entry,
    async_setup_entry,
)
from custom_components.garmin_connect.const import (
    CONF_CLIENT_ID,
    CONF_REFRESH_TOKEN,
    CONF_TOKEN,
)

_ENTRY_DATA = {
    CONF_TOKEN: "token.eyJleHAiOjk5OTk5OTk5OTl9.sig",
    CONF_REFRESH_TOKEN: "refresh",
    CONF_CLIENT_ID: "GARMIN_CONNECT_MOBILE_ANDROID_DI",
}


def _mock_coordinator():
    """Return a mock coordinator with async_config_entry_first_refresh."""
    c = MagicMock()
    c.async_config_entry_first_refresh = AsyncMock()
    return c


def _coordinator_patches():
    """Return context managers that patch all coordinator constructors."""
    c = _mock_coordinator()
    names = [
        "CoreCoordinator",
        "ActivityCoordinator",
        "TrainingCoordinator",
        "BodyCoordinator",
        "GoalsCoordinator",
        "GearCoordinator",
        "BloodPressureCoordinator",
        "MenstrualCoordinator",
    ]
    return [
        patch(f"custom_components.garmin_connect.{n}", return_value=c)
        for n in names
    ]


async def test_setup_entry_success() -> None:
    """Test that a config entry sets up correctly."""
    mock_entry = MagicMock()
    mock_entry.data = _ENTRY_DATA
    mock_hass = MagicMock()
    mock_hass.config.country = "US"

    mock_auth = MagicMock()
    mock_auth.di_token = _ENTRY_DATA[CONF_TOKEN]
    mock_auth.di_refresh_token = _ENTRY_DATA[CONF_REFRESH_TOKEN]
    mock_auth.di_client_id = _ENTRY_DATA[CONF_CLIENT_ID]

    with ExitStack() as stack:
        stack.enter_context(patch("custom_components.garmin_connect.GarminAuth", return_value=mock_auth))
        stack.enter_context(patch("custom_components.garmin_connect.GarminClient"))
        for p in _coordinator_patches():
            stack.enter_context(p)
        stack.enter_context(patch.object(
            mock_hass.config_entries,
            "async_forward_entry_setups",
            new=AsyncMock(),
        ))
        result = await async_setup_entry(mock_hass, mock_entry)

    assert result is True
    assert mock_entry.runtime_data is not None


async def test_setup_entry_restores_tokens_from_entry() -> None:
    """Test that tokens are restored from config entry data."""
    mock_entry = MagicMock()
    mock_entry.data = _ENTRY_DATA
    mock_hass = MagicMock()
    mock_hass.config.country = "US"

    captured_auth = {}

    def capture_auth(is_cn=False):
        auth = MagicMock()
        captured_auth["instance"] = auth
        return auth

    with ExitStack() as stack:
        stack.enter_context(patch("custom_components.garmin_connect.GarminAuth", side_effect=capture_auth))
        stack.enter_context(patch("custom_components.garmin_connect.GarminClient"))
        for p in _coordinator_patches():
            stack.enter_context(p)
        stack.enter_context(patch.object(
            mock_hass.config_entries,
            "async_forward_entry_setups",
            new=AsyncMock(),
        ))
        await async_setup_entry(mock_hass, mock_entry)

    auth = captured_auth["instance"]
    assert auth.di_token == _ENTRY_DATA[CONF_TOKEN]
    assert auth.di_refresh_token == _ENTRY_DATA[CONF_REFRESH_TOKEN]
    assert auth.di_client_id == _ENTRY_DATA[CONF_CLIENT_ID]


# ── Migration tests ─────────────────────────────────────────────────────────


async def test_migrate_v1_to_v2_bumps_version_and_triggers_reauth() -> None:
    """Test that v1 entries are bumped to v2 and reauth is triggered."""
    mock_entry = MagicMock()
    mock_entry.version = 1
    mock_entry.unique_id = "user@example.com"
    mock_entry.entry_id = "test_entry_id"
    mock_entry.title = "user@example.com"

    mock_hass = MagicMock()

    # No entities to migrate
    with patch(
        "custom_components.garmin_connect.er.async_get"
    ), patch(
        "custom_components.garmin_connect.er.async_entries_for_config_entry",
        return_value=[],
    ):
        result = await async_migrate_entry(mock_hass, mock_entry)

    assert result is True
    mock_hass.config_entries.async_update_entry.assert_called_once_with(
        mock_entry, version=2
    )
    mock_entry.async_start_reauth.assert_called_once_with(mock_hass)


async def test_migrate_v2_is_noop() -> None:
    """Test that v2 entries are not migrated again."""
    mock_entry = MagicMock()
    mock_entry.version = 2

    mock_hass = MagicMock()

    result = await async_migrate_entry(mock_hass, mock_entry)

    assert result is True
    mock_hass.config_entries.async_update_entry.assert_not_called()


async def test_migrate_entity_unique_ids_unchanged_key() -> None:
    """Test that entities with unchanged keys get prefix migrated."""
    mock_hass = MagicMock()
    mock_entry = MagicMock()
    mock_entry.entry_id = "new_entry_id"

    old_prefix = "user@example.com"

    mock_entity = MagicMock()
    mock_entity.unique_id = f"{old_prefix}_totalSteps"
    mock_entity.entity_id = "sensor.total_steps"

    mock_registry = MagicMock()

    with patch(
        "custom_components.garmin_connect.er.async_get",
        return_value=mock_registry,
    ), patch(
        "custom_components.garmin_connect.er.async_entries_for_config_entry",
        return_value=[mock_entity],
    ):
        _migrate_entity_unique_ids(mock_hass, mock_entry, old_prefix)

    mock_registry.async_update_entity.assert_called_once_with(
        "sensor.total_steps",
        new_unique_id="new_entry_id_totalSteps",
    )


async def test_migrate_entity_unique_ids_renamed_key() -> None:
    """Test that entities with renamed keys get both prefix and key migrated."""
    mock_hass = MagicMock()
    mock_entry = MagicMock()
    mock_entry.entry_id = "new_entry_id"

    old_prefix = "user@example.com"

    mock_entity = MagicMock()
    mock_entity.unique_id = f"{old_prefix}_sleepingSeconds"
    mock_entity.entity_id = "sensor.sleeping_time"

    mock_registry = MagicMock()

    with patch(
        "custom_components.garmin_connect.er.async_get",
        return_value=mock_registry,
    ), patch(
        "custom_components.garmin_connect.er.async_entries_for_config_entry",
        return_value=[mock_entity],
    ):
        _migrate_entity_unique_ids(mock_hass, mock_entry, old_prefix)

    mock_registry.async_update_entity.assert_called_once_with(
        "sensor.sleeping_time",
        new_unique_id="new_entry_id_sleepingMinutes",
    )


async def test_migrate_entity_unique_ids_dropped_key_skipped() -> None:
    """Test that dropped sensors are skipped during migration."""
    mock_hass = MagicMock()
    mock_entry = MagicMock()
    mock_entry.entry_id = "new_entry_id"

    old_prefix = "user@example.com"

    mock_entity = MagicMock()
    mock_entity.unique_id = f"{old_prefix}_netCalorieGoal"
    mock_entity.entity_id = "sensor.net_calorie_goal"

    mock_registry = MagicMock()

    with patch(
        "custom_components.garmin_connect.er.async_get",
        return_value=mock_registry,
    ), patch(
        "custom_components.garmin_connect.er.async_entries_for_config_entry",
        return_value=[mock_entity],
    ):
        _migrate_entity_unique_ids(mock_hass, mock_entry, old_prefix)

    mock_registry.async_update_entity.assert_not_called()


async def test_migrate_entity_unique_ids_conflict_handled() -> None:
    """Test that unique_id conflicts are logged but don't fail migration."""
    mock_hass = MagicMock()
    mock_entry = MagicMock()
    mock_entry.entry_id = "new_entry_id"

    old_prefix = "user@example.com"

    mock_entity = MagicMock()
    mock_entity.unique_id = f"{old_prefix}_totalSteps"
    mock_entity.entity_id = "sensor.total_steps"

    mock_registry = MagicMock()
    mock_registry.async_update_entity.side_effect = ValueError("conflict")

    with patch(
        "custom_components.garmin_connect.er.async_get",
        return_value=mock_registry,
    ), patch(
        "custom_components.garmin_connect.er.async_entries_for_config_entry",
        return_value=[mock_entity],
    ):
        # Should not raise
        _migrate_entity_unique_ids(mock_hass, mock_entry, old_prefix)

    mock_registry.async_update_entity.assert_called_once()


async def test_migrate_entity_non_matching_prefix_skipped() -> None:
    """Test that entities not matching the old prefix are skipped."""
    mock_hass = MagicMock()
    mock_entry = MagicMock()
    mock_entry.entry_id = "new_entry_id"

    old_prefix = "user@example.com"

    mock_entity = MagicMock()
    mock_entity.unique_id = "other_prefix_totalSteps"
    mock_entity.entity_id = "sensor.total_steps"

    mock_registry = MagicMock()

    with patch(
        "custom_components.garmin_connect.er.async_get",
        return_value=mock_registry,
    ), patch(
        "custom_components.garmin_connect.er.async_entries_for_config_entry",
        return_value=[mock_entity],
    ):
        _migrate_entity_unique_ids(mock_hass, mock_entry, old_prefix)

    mock_registry.async_update_entity.assert_not_called()


async def test_migrate_multiple_accounts() -> None:
    """Test that migration works correctly with multiple accounts."""
    mock_hass = MagicMock()

    entries = []
    for email, entry_id in [
        ("user1@example.com", "entry_1"),
        ("user2@example.com", "entry_2"),
    ]:
        mock_entry = MagicMock()
        mock_entry.version = 1
        mock_entry.unique_id = email
        mock_entry.entry_id = entry_id
        mock_entry.title = email

        mock_entity = MagicMock()
        mock_entity.unique_id = f"{email}_totalSteps"
        mock_entity.entity_id = (
            "sensor.total_steps" if email == "user1@example.com"
            else "sensor.total_steps_2"
        )

        mock_registry = MagicMock()

        with patch(
            "custom_components.garmin_connect.er.async_get",
            return_value=mock_registry,
        ), patch(
            "custom_components.garmin_connect.er.async_entries_for_config_entry",
            return_value=[mock_entity],
        ):
            result = await async_migrate_entry(mock_hass, mock_entry)

        assert result is True
        mock_registry.async_update_entity.assert_called_once_with(
            mock_entity.entity_id,
            new_unique_id=f"{entry_id}_totalSteps",
        )
        entries.append(mock_entry)

    # Both entries got version bumped and reauth triggered
    for mock_entry in entries:
        mock_entry.async_start_reauth.assert_called_once_with(mock_hass)

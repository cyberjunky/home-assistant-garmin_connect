"""Tests for Garmin Connect diagnostics."""

from unittest.mock import MagicMock

from custom_components.garmin_connect.diagnostics import (
    TO_REDACT,
    async_get_config_entry_diagnostics,
)


async def test_diagnostics_redacts_sensitive_data() -> None:
    """Test that diagnostics redacts tokens, names, and email."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = {"totalSteps": 10000, "restingHeartRate": 60}
    mock_coordinator.last_update_success = True
    mock_coordinator.update_interval.total_seconds.return_value = 300

    mock_coordinators = MagicMock()
    # Make dataclasses.fields work by providing _fields on the spec
    mock_field = MagicMock()
    mock_field.name = "core"

    entry_data = {
        "token": "secret_token",
        "refresh_token": "secret_refresh",
        "client_id": "secret_client_id",
        "username": "test@example.com",
    }

    mock_entry = MagicMock()
    mock_entry.data = entry_data
    mock_entry.runtime_data = mock_coordinators
    mock_entry.runtime_data.core = mock_coordinator

    mock_hass = MagicMock()

    # Patch dataclass fields to return our mock field
    from unittest.mock import patch

    with patch(
        "custom_components.garmin_connect.diagnostics.fields",
        return_value=[mock_field],
    ):
        result = await async_get_config_entry_diagnostics(mock_hass, mock_entry)

    assert "entry_data" in result
    assert "coordinators" in result
    # Redacted fields should be replaced
    assert result["entry_data"]["token"] == "**REDACTED**"
    assert result["entry_data"]["refresh_token"] == "**REDACTED**"
    assert result["entry_data"]["client_id"] == "**REDACTED**"
    # Non-redacted fields should remain
    assert result["entry_data"]["username"] == "test@example.com"


async def test_diagnostics_coordinator_info() -> None:
    """Test that diagnostics includes coordinator info."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = {"key1": "val", "key2": "val"}
    mock_coordinator.last_update_success = True
    mock_coordinator.update_interval.total_seconds.return_value = 300

    mock_field = MagicMock()
    mock_field.name = "core"

    mock_entry = MagicMock()
    mock_entry.data = {}
    mock_entry.runtime_data = MagicMock()
    mock_entry.runtime_data.core = mock_coordinator

    mock_hass = MagicMock()

    from unittest.mock import patch

    with patch(
        "custom_components.garmin_connect.diagnostics.fields",
        return_value=[mock_field],
    ):
        result = await async_get_config_entry_diagnostics(mock_hass, mock_entry)

    core_info = result["coordinators"]["core"]
    assert core_info["last_update_success"] is True
    assert core_info["update_interval_seconds"] == 300
    assert core_info["data_keys_count"] == 2
    assert core_info["data_keys_sample"] == ["key1", "key2"]


async def test_diagnostics_handles_none_update_interval() -> None:
    """Test that diagnostics handles coordinator with no update interval."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = {}
    mock_coordinator.last_update_success = False
    mock_coordinator.update_interval = None

    mock_field = MagicMock()
    mock_field.name = "core"

    mock_entry = MagicMock()
    mock_entry.data = {}
    mock_entry.runtime_data = MagicMock()
    mock_entry.runtime_data.core = mock_coordinator

    mock_hass = MagicMock()

    from unittest.mock import patch

    with patch(
        "custom_components.garmin_connect.diagnostics.fields",
        return_value=[mock_field],
    ):
        result = await async_get_config_entry_diagnostics(mock_hass, mock_entry)

    assert result["coordinators"]["core"]["update_interval_seconds"] is None


def test_to_redact_contains_expected_keys() -> None:
    """Test that the redaction set covers all sensitive fields."""
    expected = {
        "token",
        "refresh_token",
        "client_id",
        "displayName",
        "fullName",
        "userName",
        "email",
        "profileImageUrlMedium",
        "profileImageUrlSmall",
        "profileImageUrlLarge",
    }
    assert TO_REDACT == expected

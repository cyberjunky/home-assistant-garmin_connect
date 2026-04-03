"""Tests for Garmin Connect integration setup."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.garmin_connect.const import (
    CONF_DI_CLIENT_ID,
    CONF_DI_REFRESH_TOKEN,
    CONF_DI_TOKEN,
    DOMAIN,
)

_ENTRY_DATA = {
    CONF_DI_TOKEN: "token.eyJleHAiOjk5OTk5OTk5OTl9.sig",
    CONF_DI_REFRESH_TOKEN: "refresh",
    CONF_DI_CLIENT_ID: "GARMIN_CONNECT_MOBILE_ANDROID_DI",
}


async def test_setup_entry_success() -> None:
    """Test that a config entry sets up correctly."""
    from custom_components.garmin_connect import async_setup_entry

    mock_entry = MagicMock()
    mock_entry.data = _ENTRY_DATA
    mock_hass = MagicMock()
    mock_hass.config.country = "US"

    mock_auth = MagicMock()
    mock_auth.di_token = _ENTRY_DATA[CONF_DI_TOKEN]
    mock_auth.di_refresh_token = _ENTRY_DATA[CONF_DI_REFRESH_TOKEN]
    mock_auth.di_client_id = _ENTRY_DATA[CONF_DI_CLIENT_ID]

    mock_coordinator = MagicMock()
    mock_coordinator.async_config_entry_first_refresh = AsyncMock()

    with (
        patch("custom_components.garmin_connect.GarminAuth", return_value=mock_auth),
        patch("custom_components.garmin_connect.GarminClient"),
        patch(
            "custom_components.garmin_connect.CoreCoordinator",
            return_value=mock_coordinator,
        ),
        patch.object(
            mock_hass.config_entries,
            "async_forward_entry_setups",
            new=AsyncMock(),
        ),
    ):
        result = await async_setup_entry(mock_hass, mock_entry)

    assert result is True
    assert mock_entry.runtime_data is not None


async def test_setup_entry_restores_di_tokens_from_entry() -> None:
    """Test that DI tokens are restored from config entry data."""
    from custom_components.garmin_connect import async_setup_entry

    mock_entry = MagicMock()
    mock_entry.data = _ENTRY_DATA
    mock_hass = MagicMock()
    mock_hass.config.country = "US"

    captured_auth = {}

    def capture_auth(is_cn=False):
        auth = MagicMock()
        captured_auth["instance"] = auth
        return auth

    mock_coordinator = MagicMock()
    mock_coordinator.async_config_entry_first_refresh = AsyncMock()

    with (
        patch("custom_components.garmin_connect.GarminAuth", side_effect=capture_auth),
        patch("custom_components.garmin_connect.GarminClient"),
        patch(
            "custom_components.garmin_connect.CoreCoordinator",
            return_value=mock_coordinator,
        ),
        patch.object(
            mock_hass.config_entries,
            "async_forward_entry_setups",
            new=AsyncMock(),
        ),
    ):
        await async_setup_entry(mock_hass, mock_entry)

    auth = captured_auth["instance"]
    assert auth.di_token == _ENTRY_DATA[CONF_DI_TOKEN]
    assert auth.di_refresh_token == _ENTRY_DATA[CONF_DI_REFRESH_TOKEN]
    assert auth.di_client_id == _ENTRY_DATA[CONF_DI_CLIENT_ID]


async def test_migrate_entry_v1_to_v2_updates_unique_id() -> None:
    """Test that v1 entries migrate unique_id from email to profile_id."""
    from custom_components.garmin_connect import async_migrate_entry

    mock_profile = MagicMock()
    mock_profile.profile_id = 82413233

    mock_client = MagicMock()
    mock_client.get_user_profile = AsyncMock(return_value=mock_profile)

    mock_entry = MagicMock()
    mock_entry.version = 1
    mock_entry.unique_id = "user@example.com"
    mock_entry.data = _ENTRY_DATA
    mock_hass = MagicMock()
    mock_hass.config.country = "US"

    with (
        patch("custom_components.garmin_connect.GarminAuth"),
        patch("custom_components.garmin_connect.GarminClient", return_value=mock_client),
    ):
        result = await async_migrate_entry(mock_hass, mock_entry)

    assert result is True
    mock_hass.config_entries.async_update_entry.assert_called_once_with(
        mock_entry, unique_id="82413233", version=2
    )


async def test_migrate_entry_v1_to_v2_keeps_existing_unique_id_on_error() -> None:
    """Test that v1 migration keeps existing unique_id if profile fetch fails."""
    from ha_garmin.exceptions import GarminConnectError

    from custom_components.garmin_connect import async_migrate_entry

    mock_client = MagicMock()
    mock_client.get_user_profile = AsyncMock(side_effect=GarminConnectError("fail"))

    mock_entry = MagicMock()
    mock_entry.version = 1
    mock_entry.unique_id = "user@example.com"
    mock_entry.data = _ENTRY_DATA
    mock_hass = MagicMock()
    mock_hass.config.country = "US"

    with (
        patch("custom_components.garmin_connect.GarminAuth"),
        patch("custom_components.garmin_connect.GarminClient", return_value=mock_client),
    ):
        result = await async_migrate_entry(mock_hass, mock_entry)

    assert result is True
    mock_hass.config_entries.async_update_entry.assert_called_once_with(
        mock_entry, unique_id="user@example.com", version=2
    )


async def test_migrate_entry_no_di_token_triggers_reauth() -> None:
    """Test that entries without DI token trigger reauth and return False."""
    from custom_components.garmin_connect import async_migrate_entry

    mock_entry = MagicMock()
    mock_entry.version = 1
    mock_entry.data = {}  # no DI token
    mock_hass = MagicMock()

    result = await async_migrate_entry(mock_hass, mock_entry)

    assert result is False
    mock_entry.async_start_reauth.assert_called_once_with(mock_hass)

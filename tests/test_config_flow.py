"""Tests for Garmin Connect config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

from ha_garmin import GarminAuthError, GarminMFARequired
import pytest

from custom_components.garmin_connect.const import (
    CONF_DI_CLIENT_ID,
    CONF_DI_REFRESH_TOKEN,
    CONF_DI_TOKEN,
    DOMAIN,
)


def _make_mock_auth(*, raise_on_login=None):
    """Build a mock GarminAuth with DI tokens set."""
    auth = MagicMock()
    auth.di_token = "token.eyJleHAiOjk5OTk5OTk5OTl9.sig"
    auth.di_refresh_token = "refresh_token"
    auth.di_client_id = "GARMIN_CONNECT_MOBILE_ANDROID_DI"
    auth.login = AsyncMock(side_effect=raise_on_login) if raise_on_login else AsyncMock()
    auth.complete_mfa = AsyncMock()
    return auth


async def test_form_shows_initial_step() -> None:
    """Test that the initial step shows the login form."""
    from custom_components.garmin_connect.config_flow import GarminConnectConfigFlow

    flow = GarminConnectConfigFlow()
    result = await flow.async_step_user(None)
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_login_invalid_auth() -> None:
    """Test invalid auth sets the correct error."""
    from custom_components.garmin_connect.config_flow import GarminConnectConfigFlow

    mock_auth = _make_mock_auth(raise_on_login=GarminAuthError("bad creds"))
    flow = GarminConnectConfigFlow()
    flow.hass = MagicMock()
    flow.hass.config.country = "US"

    with patch("custom_components.garmin_connect.config_flow.GarminAuth", return_value=mock_auth):
        result = await flow.async_step_user(
            {"username": "test@example.com", "password": "wrong"}
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_login_mfa_required_transitions_to_mfa_step() -> None:
    """Test that MFA required transitions to the MFA step."""
    from custom_components.garmin_connect.config_flow import GarminConnectConfigFlow

    mock_auth = _make_mock_auth(raise_on_login=GarminMFARequired("mfa_ticket"))
    flow = GarminConnectConfigFlow()
    flow.hass = MagicMock()
    flow.hass.config.country = "US"

    with patch("custom_components.garmin_connect.config_flow.GarminAuth", return_value=mock_auth):
        result = await flow.async_step_user(
            {"username": "test@example.com", "password": "pass"}
        )

    assert result["type"] == "form"
    assert result["step_id"] == "mfa"


async def test_mfa_invalid_code_sets_error() -> None:
    """Test that an invalid MFA code sets an error."""
    from custom_components.garmin_connect.config_flow import GarminConnectConfigFlow

    flow = GarminConnectConfigFlow()
    flow.hass = MagicMock()
    flow._auth = MagicMock()
    flow._auth.complete_mfa = AsyncMock(side_effect=GarminAuthError("bad code"))

    result = await flow.async_step_mfa({"mfa_code": "000000"})

    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_mfa"}


async def test_no_bare_except_in_flow() -> None:
    """Ensure config_flow never uses bare except Exception."""
    import inspect

    from custom_components.garmin_connect import config_flow

    source = inspect.getsource(config_flow)
    assert "except Exception" not in source


async def test_login_uses_async_api() -> None:
    """Login must call auth.login directly (async API, not executor)."""
    import inspect

    from custom_components.garmin_connect import config_flow

    source = inspect.getsource(config_flow.GarminConnectConfigFlow.async_step_user)
    assert "await self._auth.login(" in source
    assert "async_add_executor_job" not in source

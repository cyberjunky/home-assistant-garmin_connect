"""Tests for Garmin Connect config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

from ha_garmin import GarminAuthError, GarminConnectError, GarminMFARequired, GarminRateLimitError

from custom_components.garmin_connect.const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
)

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_auth_mock(*, login_side_effect=None) -> MagicMock:
    """Build a mock GarminAuth with DI tokens set."""
    auth = MagicMock()
    auth.di_token = "token.eyJleHAiOjk5OTk5OTk5OTl9.sig"
    auth.di_refresh_token = "refresh_token"
    auth.di_client_id = "GARMIN_CONNECT_MOBILE_ANDROID_DI"
    # login/complete_mfa are called via executor (sync callables)
    auth.login = MagicMock(side_effect=login_side_effect)
    auth.complete_mfa = MagicMock()
    return auth


def _sync_call(fn, *args):
    """Simulate executor_job: call sync fn and propagate exceptions."""
    fn(*args)


# ── User step ─────────────────────────────────────────────────────────────────


async def test_user_step_shows_form() -> None:
    """Initial step must show the login form with no errors."""
    from custom_components.garmin_connect.config_flow import GarminConnectConfigFlow

    flow = GarminConnectConfigFlow()
    result = await flow.async_step_user(None)

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_user_step_invalid_auth() -> None:
    """Invalid credentials must set base error and re-show the form."""
    from custom_components.garmin_connect.config_flow import GarminConnectConfigFlow

    auth = _make_auth_mock(login_side_effect=GarminAuthError("bad creds"))
    flow = GarminConnectConfigFlow()
    flow.hass = MagicMock()
    flow.hass.config.country = "US"
    flow.hass.async_add_executor_job = AsyncMock(side_effect=lambda fn, *a: _sync_call(fn, *a))

    with patch("custom_components.garmin_connect.config_flow.GarminAuth", return_value=auth):
        result = await flow.async_step_user({"username": "test@example.com", "password": "wrong"})

    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_step_garmin_connect_error() -> None:
    """GarminConnectError must map to the 'unknown' base error."""
    from custom_components.garmin_connect.config_flow import GarminConnectConfigFlow

    auth = _make_auth_mock(login_side_effect=GarminConnectError("timeout"))
    flow = GarminConnectConfigFlow()
    flow.hass = MagicMock()
    flow.hass.config.country = "US"
    flow.hass.async_add_executor_job = AsyncMock(side_effect=lambda fn, *a: _sync_call(fn, *a))

    with patch("custom_components.garmin_connect.config_flow.GarminAuth", return_value=auth):
        result = await flow.async_step_user({"username": "test@example.com", "password": "pass"})

    assert result["type"] == "form"
    assert result["errors"] == {"base": "unknown"}


async def test_user_step_rate_limit() -> None:
    """GarminRateLimitError must set the rate_limit base error."""
    from custom_components.garmin_connect.config_flow import GarminConnectConfigFlow

    auth = _make_auth_mock(login_side_effect=GarminRateLimitError("429"))
    flow = GarminConnectConfigFlow()
    flow.hass = MagicMock()
    flow.hass.config.country = "US"
    flow.hass.async_add_executor_job = AsyncMock(side_effect=lambda fn, *a: _sync_call(fn, *a))

    with patch("custom_components.garmin_connect.config_flow.GarminAuth", return_value=auth):
        result = await flow.async_step_user({"username": "test@example.com", "password": "pass"})

    assert result["type"] == "form"
    assert result["errors"] == {"base": "rate_limit"}


async def test_user_step_mfa_required_transitions() -> None:
    """GarminMFARequired must move the flow to the mfa step."""
    from custom_components.garmin_connect.config_flow import GarminConnectConfigFlow

    auth = _make_auth_mock(login_side_effect=GarminMFARequired("ticket"))
    flow = GarminConnectConfigFlow()
    flow.hass = MagicMock()
    flow.hass.config.country = "US"
    flow.hass.async_add_executor_job = AsyncMock(side_effect=lambda fn, *a: _sync_call(fn, *a))

    with patch("custom_components.garmin_connect.config_flow.GarminAuth", return_value=auth):
        result = await flow.async_step_user({"username": "test@example.com", "password": "pass"})

    assert result["type"] == "form"
    assert result["step_id"] == "mfa"


# ── MFA step ──────────────────────────────────────────────────────────────────


async def test_mfa_step_invalid_code() -> None:
    """An invalid MFA code must set base error and re-show the MFA form."""
    from custom_components.garmin_connect.config_flow import GarminConnectConfigFlow

    flow = GarminConnectConfigFlow()
    flow.hass = MagicMock()
    flow._auth = MagicMock()
    flow._auth.complete_mfa = MagicMock(side_effect=GarminAuthError("bad code"))
    flow.hass.async_add_executor_job = AsyncMock(side_effect=lambda fn, *a: _sync_call(fn, *a))

    result = await flow.async_step_mfa({"mfa_code": "000000"})

    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_mfa"}


async def test_mfa_step_rate_limit() -> None:
    """GarminRateLimitError during MFA must set the rate_limit base error."""
    from custom_components.garmin_connect.config_flow import GarminConnectConfigFlow

    flow = GarminConnectConfigFlow()
    flow.hass = MagicMock()
    flow._auth = MagicMock()
    flow._auth.complete_mfa = MagicMock(side_effect=GarminRateLimitError("429"))
    flow.hass.async_add_executor_job = AsyncMock(side_effect=lambda fn, *a: _sync_call(fn, *a))

    result = await flow.async_step_mfa({"mfa_code": "000000"})

    assert result["type"] == "form"
    assert result["errors"] == {"base": "rate_limit"}


# ── Reauth / Reconfigure steps ────────────────────────────────────────────────


async def test_reauth_confirm_step_shows_form() -> None:
    """Reauth confirm step must show the re-authentication form."""
    from homeassistant.config_entries import SOURCE_REAUTH

    from custom_components.garmin_connect.config_flow import GarminConnectConfigFlow

    mock_entry = MagicMock()
    mock_entry.options = {}
    flow = GarminConnectConfigFlow()
    flow.hass = MagicMock()
    flow.hass.config_entries.async_get_known_entry.return_value = mock_entry
    flow.context = {"source": SOURCE_REAUTH, "entry_id": "test_entry_id"}

    result = await flow.async_step_reauth_confirm(None)

    assert result["type"] == "form"
    assert result["step_id"] == "reauth_confirm"


async def test_reconfigure_step_shows_form() -> None:
    """Reconfigure step must show the reconfiguration form."""
    from homeassistant.config_entries import SOURCE_RECONFIGURE

    from custom_components.garmin_connect.config_flow import GarminConnectConfigFlow

    mock_entry = MagicMock()
    mock_entry.options = {}
    flow = GarminConnectConfigFlow()
    flow.hass = MagicMock()
    flow.hass.config_entries.async_get_known_entry.return_value = mock_entry
    flow.context = {"source": SOURCE_RECONFIGURE, "entry_id": "test_entry_id"}

    result = await flow.async_step_reconfigure(None)

    assert result["type"] == "form"
    assert result["step_id"] == "reconfigure"


# ── Options flow ──────────────────────────────────────────────────────────────


def _make_options_flow(options: dict):
    """Instantiate GarminConnectOptionsFlow with a fake config_entry."""
    from custom_components.garmin_connect.config_flow import GarminConnectOptionsFlow

    entry = MagicMock()
    entry.options = options

    flow = GarminConnectOptionsFlow()
    # OptionsFlow._config_entry_id returns self.handler; config_entry calls
    # hass.config_entries.async_get_known_entry(_config_entry_id).
    flow.handler = "test_entry_id"
    hass = MagicMock()
    hass.config_entries.async_get_known_entry = MagicMock(return_value=entry)
    flow.hass = hass
    return flow


async def test_options_flow_shows_form() -> None:
    """Options flow init step must show the scan_interval form."""
    flow = _make_options_flow({CONF_SCAN_INTERVAL: 600})
    result = await flow.async_step_init(None)

    assert result["type"] == "form"
    assert result["step_id"] == "init"


async def test_options_flow_saves_new_interval() -> None:
    """Submitting the options form must create an entry with the chosen interval."""
    flow = _make_options_flow({CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL})
    result = await flow.async_step_init({CONF_SCAN_INTERVAL: 120})

    assert result["type"] == "create_entry"
    assert result["data"][CONF_SCAN_INTERVAL] == 120


async def test_options_flow_uses_default_when_options_empty() -> None:
    """Options flow must fall back to DEFAULT_SCAN_INTERVAL when entry options is empty."""
    flow = _make_options_flow({})

    # Just check the form renders without error; schema carries the default
    result = await flow.async_step_init(None)
    assert result["type"] == "form"


# ── Reauth account verification ───────────────────────────────────────────────


def _reauth_flow(entry_unique_id: str | None, profile_id: str | None = "123456789"):
    """Flow that has just logged in as test@example.com during reauth."""
    from homeassistant.config_entries import SOURCE_REAUTH

    from custom_components.garmin_connect.config_flow import GarminConnectConfigFlow

    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.unique_id = entry_unique_id
    entry.options = {}
    flow = GarminConnectConfigFlow()
    flow.hass = MagicMock()
    flow.hass.config_entries.async_reload = AsyncMock()
    flow.hass.config_entries.async_get_known_entry.return_value = entry
    flow.context = {"source": SOURCE_REAUTH, "entry_id": "test_entry_id"}
    flow._auth = _make_auth_mock()
    flow._username = "test@example.com"

    client = MagicMock()
    if profile_id is None:
        client.get_user_profile = AsyncMock(side_effect=GarminConnectError("down"))
    else:
        client.get_user_profile = AsyncMock(return_value=MagicMock(profile_id=int(profile_id)))
    return flow, entry, client


async def test_reauth_with_other_account_aborts() -> None:
    """Logging in with a different Garmin account must not hijack the entry."""
    flow, entry, client = _reauth_flow("999", profile_id="123456789")
    with patch("custom_components.garmin_connect.config_flow.GarminClient", return_value=client):
        result = await flow._async_finish_reauth()

    assert result["type"] == "abort"
    assert result["reason"] == "wrong_account"
    flow.hass.config_entries.async_update_entry.assert_not_called()
    flow.hass.config_entries.async_reload.assert_not_awaited()


async def test_reauth_same_account_updates_tokens_and_reloads() -> None:
    flow, entry, client = _reauth_flow("123456789")
    with patch("custom_components.garmin_connect.config_flow.GarminClient", return_value=client):
        result = await flow._async_finish_reauth()

    assert result["type"] == "abort"
    assert result["reason"] == "reauth_successful"
    _, kwargs = flow.hass.config_entries.async_update_entry.call_args
    assert kwargs["data"]["token"] == flow._auth.di_token
    flow.hass.config_entries.async_reload.assert_awaited_once_with("test_entry_id")


async def test_reauth_upgrades_legacy_email_unique_id() -> None:
    """Entries keyed by email (pre-profile-id) are accepted and re-keyed by profile id."""
    flow, entry, client = _reauth_flow("Test@Example.com")
    with patch("custom_components.garmin_connect.config_flow.GarminClient", return_value=client):
        result = await flow._async_finish_reauth()

    assert result["reason"] == "reauth_successful"
    flow.hass.config_entries.async_update_entry.assert_any_call(entry, unique_id="123456789")


async def test_reauth_retries_when_profile_unavailable() -> None:
    """Without a profile the account cannot be verified; the entry must stay untouched."""
    flow, entry, client = _reauth_flow("999", profile_id=None)
    with patch("custom_components.garmin_connect.config_flow.GarminClient", return_value=client):
        result = await flow._async_finish_reauth()

    assert result["type"] == "form"
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": "profile_unavailable"}
    flow.hass.config_entries.async_update_entry.assert_not_called()
    flow.hass.config_entries.async_reload.assert_not_awaited()


async def test_reauth_legacy_email_entry_proceeds_when_profile_unavailable() -> None:
    """A matching legacy email unique_id verifies the account without a profile."""
    flow, entry, client = _reauth_flow("Test@Example.com", profile_id=None)
    with patch("custom_components.garmin_connect.config_flow.GarminClient", return_value=client):
        result = await flow._async_finish_reauth()

    assert result["reason"] == "reauth_successful"
    _, kwargs = flow.hass.config_entries.async_update_entry.call_args
    assert kwargs["data"]["token"] == flow._auth.di_token
    flow.hass.config_entries.async_reload.assert_awaited_once_with("test_entry_id")


async def test_reconfigure_retries_when_profile_unavailable() -> None:
    from homeassistant.config_entries import SOURCE_RECONFIGURE

    flow, entry, client = _reauth_flow("999", profile_id=None)
    flow.context = {"source": SOURCE_RECONFIGURE, "entry_id": "test_entry_id"}
    with patch("custom_components.garmin_connect.config_flow.GarminClient", return_value=client):
        result = await flow._async_finish_reconfigure()

    assert result["type"] == "form"
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": "profile_unavailable"}
    flow.hass.config_entries.async_update_entry.assert_not_called()


async def test_reconfigure_with_other_account_aborts() -> None:
    from homeassistant.config_entries import SOURCE_RECONFIGURE

    flow, entry, client = _reauth_flow("999")
    flow.context = {"source": SOURCE_RECONFIGURE, "entry_id": "test_entry_id"}
    with patch("custom_components.garmin_connect.config_flow.GarminClient", return_value=client):
        result = await flow._async_finish_reconfigure()

    assert result["reason"] == "wrong_account"

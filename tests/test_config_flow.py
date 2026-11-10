"""Tests for the Garmin Connect config flow, run through Home Assistant."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from ha_garmin import GarminAuthError, GarminConnectError, GarminMFARequired, GarminRateLimitError
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant.common import MockConfigEntry

from custom_components.garmin_connect.const import (
    CONF_CLIENT_ID,
    CONF_IS_CN,
    CONF_REFRESH_TOKEN,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")

PROFILE_ID = "123456789"
USER_INPUT = {CONF_USERNAME: "Test@Example.com", CONF_PASSWORD: "secret"}
NEW_TOKENS = {
    CONF_TOKEN: "new_token",
    CONF_REFRESH_TOKEN: "new_refresh_token",
    CONF_CLIENT_ID: "GARMIN_CONNECT_MOBILE_ANDROID_DI",
}

LOGIN_ERRORS = [
    (GarminAuthError("bad credentials"), "invalid_auth"),
    (GarminRateLimitError("429"), "rate_limit"),
    (GarminConnectError("network down"), "cannot_connect"),
    (RuntimeError("boom"), "unknown"),
]
MFA_ERRORS = [
    (GarminAuthError("bad code"), "invalid_mfa"),
    (GarminRateLimitError("429"), "rate_limit"),
    (GarminConnectError("network down"), "cannot_connect"),
    (RuntimeError("boom"), "unknown"),
]


@pytest.fixture(autouse=True)
def _flow_environment(hass: HomeAssistant) -> Generator[None]:
    """Load the integration's flows without its frontend/http dependencies.

    Entry setup is stubbed: reauth and reconfigure reload the entry, and these
    tests are about the flow, not about polling Garmin.
    """
    hass.config.components.update({"frontend", "http"})
    with (
        patch("custom_components.garmin_connect.async_setup", return_value=True),
        patch("custom_components.garmin_connect.async_setup_entry", return_value=True),
    ):
        yield


@pytest.fixture
def mock_flow_auth() -> Generator[MagicMock]:
    """GarminAuth as seen by the config flow: login succeeds with new tokens."""
    with patch("custom_components.garmin_connect.config_flow.GarminAuth") as mock_cls:
        auth = mock_cls.return_value
        auth.di_token = NEW_TOKENS[CONF_TOKEN]
        auth.di_refresh_token = NEW_TOKENS[CONF_REFRESH_TOKEN]
        auth.di_client_id = NEW_TOKENS[CONF_CLIENT_ID]
        auth.login = AsyncMock()
        auth.complete_mfa = AsyncMock()
        auth.cancel_mfa = AsyncMock()
        yield auth


@pytest.fixture
def mock_flow_client() -> Generator[MagicMock]:
    """GarminClient as seen by the config flow: the profile lookup succeeds."""
    with patch("custom_components.garmin_connect.config_flow.GarminClient") as mock_cls:
        client = mock_cls.return_value
        client.get_user_profile = AsyncMock(return_value=MagicMock(profile_id=int(PROFILE_ID)))
        yield client


async def _start_user_flow(hass: HomeAssistant) -> str:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    return result["flow_id"]


# ── User flow ─────────────────────────────────────────────────────────────────


async def test_user_flow_creates_entry(
    hass: HomeAssistant, mock_flow_auth: MagicMock, mock_flow_client: MagicMock
) -> None:
    """A successful login creates an entry keyed by the Garmin profile id."""
    flow_id = await _start_user_flow(hass)

    result = await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == USER_INPUT[CONF_USERNAME]
    assert result["data"] == NEW_TOKENS
    assert result["options"] == {CONF_IS_CN: False}
    assert result["result"].unique_id == PROFILE_ID
    mock_flow_auth.login.assert_awaited_once_with(
        USER_INPUT[CONF_USERNAME], USER_INPUT[CONF_PASSWORD]
    )


async def test_user_flow_without_profile_uses_email(
    hass: HomeAssistant, mock_flow_auth: MagicMock, mock_flow_client: MagicMock
) -> None:
    """Without a profile the lowercased email is the unique id."""
    mock_flow_client.get_user_profile.side_effect = GarminConnectError("down")
    flow_id = await _start_user_flow(hass)

    result = await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "test@example.com"


@pytest.mark.parametrize(("exception", "error"), LOGIN_ERRORS)
async def test_user_flow_login_errors_recover(
    hass: HomeAssistant,
    mock_flow_auth: MagicMock,
    mock_flow_client: MagicMock,
    exception: Exception,
    error: str,
) -> None:
    """A failed login shows the error; a retry can still finish the flow."""
    flow_id = await _start_user_flow(hass)
    mock_flow_auth.login.side_effect = exception

    result = await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_flow_auth.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_flow_auth: MagicMock,
    mock_flow_client: MagicMock,
) -> None:
    """The same Garmin account can't be added twice."""
    mock_config_entry.add_to_hass(hass)
    flow_id = await _start_user_flow(hass)

    result = await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow_already_configured_legacy_email_entry(
    hass: HomeAssistant, mock_flow_auth: MagicMock, mock_flow_client: MagicMock
) -> None:
    """An entry still keyed by email (pre profile id) also blocks a duplicate."""
    MockConfigEntry(domain=DOMAIN, unique_id="test@example.com", data=NEW_TOKENS).add_to_hass(hass)
    flow_id = await _start_user_flow(hass)

    result = await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


# ── MFA ───────────────────────────────────────────────────────────────────────


async def test_user_flow_with_mfa(
    hass: HomeAssistant, mock_flow_auth: MagicMock, mock_flow_client: MagicMock
) -> None:
    """A login that needs MFA asks for the code and then creates the entry."""
    flow_id = await _start_user_flow(hass)
    mock_flow_auth.login.side_effect = GarminMFARequired("ticket")

    result = await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "mfa"

    result = await hass.config_entries.flow.async_configure(flow_id, {"mfa_code": "123456"})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == PROFILE_ID
    mock_flow_auth.complete_mfa.assert_awaited_once_with("123456")


@pytest.mark.parametrize(("exception", "error"), MFA_ERRORS)
async def test_mfa_failure_returns_to_login(
    hass: HomeAssistant,
    mock_flow_auth: MagicMock,
    mock_flow_client: MagicMock,
    exception: Exception,
    error: str,
) -> None:
    """Garmin's MFA session is single use, so a failed code goes back to login."""
    flow_id = await _start_user_flow(hass)
    mock_flow_auth.login.side_effect = GarminMFARequired("ticket")
    await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)
    mock_flow_auth.complete_mfa.side_effect = exception

    result = await hass.config_entries.flow.async_configure(flow_id, {"mfa_code": "000000"})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error}

    # Logging in again starts a fresh MFA session that can succeed.
    mock_flow_auth.complete_mfa.side_effect = None
    result = await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)
    assert result["step_id"] == "mfa"
    result = await hass.config_entries.flow.async_configure(flow_id, {"mfa_code": "123456"})
    assert result["type"] is FlowResultType.CREATE_ENTRY


# ── Reauth ────────────────────────────────────────────────────────────────────


async def test_reauth_updates_tokens(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_flow_auth: MagicMock,
    mock_flow_client: MagicMock,
) -> None:
    """Reauth with the same account stores the new tokens and region."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_IS_CN: True}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert dict(mock_config_entry.data) == NEW_TOKENS
    assert mock_config_entry.options[CONF_IS_CN] is True


async def test_reauth_wrong_account_aborts(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_flow_auth: MagicMock,
    mock_flow_client: MagicMock,
) -> None:
    """Logging in with another Garmin account must not take over the entry."""
    mock_config_entry.add_to_hass(hass)
    old_data = dict(mock_config_entry.data)
    mock_flow_client.get_user_profile.return_value = MagicMock(profile_id=999)
    result = await mock_config_entry.start_reauth_flow(hass)

    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"
    assert dict(mock_config_entry.data) == old_data


async def test_reauth_upgrades_legacy_email_unique_id(
    hass: HomeAssistant, mock_flow_auth: MagicMock, mock_flow_client: MagicMock
) -> None:
    """An entry keyed by email is accepted and re-keyed by profile id."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="test@example.com", data={})
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)

    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)

    assert result["reason"] == "reauth_successful"
    assert entry.unique_id == PROFILE_ID


async def test_reauth_profile_unavailable_keeps_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_flow_auth: MagicMock,
    mock_flow_client: MagicMock,
) -> None:
    """Without a profile the account can't be verified; the entry stays as is."""
    mock_config_entry.add_to_hass(hass)
    old_data = dict(mock_config_entry.data)
    mock_flow_client.get_user_profile.side_effect = GarminConnectError("down")
    result = await mock_config_entry.start_reauth_flow(hass)

    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": "profile_unavailable"}
    assert dict(mock_config_entry.data) == old_data


async def test_reauth_legacy_email_entry_without_profile(
    hass: HomeAssistant, mock_flow_auth: MagicMock, mock_flow_client: MagicMock
) -> None:
    """A matching legacy email unique id verifies the account without a profile."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="test@example.com", data={})
    entry.add_to_hass(hass)
    mock_flow_client.get_user_profile.side_effect = GarminConnectError("down")
    result = await entry.start_reauth_flow(hass)

    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)

    assert result["reason"] == "reauth_successful"
    assert dict(entry.data) == NEW_TOKENS


@pytest.mark.parametrize(("exception", "error"), LOGIN_ERRORS)
async def test_reauth_login_errors_recover(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_flow_auth: MagicMock,
    mock_flow_client: MagicMock,
    exception: Exception,
    error: str,
) -> None:
    """Reauth login errors are shown on the reauth form and can be retried."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    mock_flow_auth.login.side_effect = exception

    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": error}

    mock_flow_auth.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["reason"] == "reauth_successful"


async def test_reauth_with_mfa(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_flow_auth: MagicMock,
    mock_flow_client: MagicMock,
) -> None:
    """MFA during reauth finishes the reauth; a failed code returns to its form."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    flow_id = result["flow_id"]
    mock_flow_auth.login.side_effect = GarminMFARequired("ticket")
    await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)

    mock_flow_auth.complete_mfa.side_effect = GarminAuthError("bad code")
    result = await hass.config_entries.flow.async_configure(flow_id, {"mfa_code": "000000"})
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": "invalid_mfa"}

    mock_flow_auth.complete_mfa.side_effect = None
    await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)
    result = await hass.config_entries.flow.async_configure(flow_id, {"mfa_code": "123456"})
    assert result["reason"] == "reauth_successful"
    assert dict(mock_config_entry.data) == NEW_TOKENS


# ── Reconfigure ───────────────────────────────────────────────────────────────


async def test_reconfigure_updates_tokens(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_flow_auth: MagicMock,
    mock_flow_client: MagicMock,
) -> None:
    """Reconfigure with the same account stores the new tokens and region."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_IS_CN: True}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert dict(mock_config_entry.data) == NEW_TOKENS
    assert mock_config_entry.options[CONF_IS_CN] is True


async def test_reconfigure_wrong_account_aborts(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_flow_auth: MagicMock,
    mock_flow_client: MagicMock,
) -> None:
    """Reconfigure can't switch the entry to another Garmin account."""
    mock_config_entry.add_to_hass(hass)
    mock_flow_client.get_user_profile.return_value = MagicMock(profile_id=999)
    result = await mock_config_entry.start_reconfigure_flow(hass)

    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)

    assert result["reason"] == "wrong_account"


async def test_reconfigure_profile_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_flow_auth: MagicMock,
    mock_flow_client: MagicMock,
) -> None:
    """Without a profile reconfigure shows the form again."""
    mock_config_entry.add_to_hass(hass)
    mock_flow_client.get_user_profile.side_effect = GarminConnectError("down")
    result = await mock_config_entry.start_reconfigure_flow(hass)

    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)

    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": "profile_unavailable"}


async def test_reconfigure_mfa_failure_returns_to_reconfigure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_flow_auth: MagicMock,
    mock_flow_client: MagicMock,
) -> None:
    """A failed MFA code during reconfigure goes back to the reconfigure form."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)
    flow_id = result["flow_id"]
    mock_flow_auth.login.side_effect = GarminMFARequired("ticket")
    await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)
    mock_flow_auth.complete_mfa.side_effect = GarminAuthError("bad code")

    result = await hass.config_entries.flow.async_configure(flow_id, {"mfa_code": "000000"})

    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": "invalid_mfa"}


# ── Options flow ──────────────────────────────────────────────────────────────


async def test_options_flow_saves_interval_and_keeps_region(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """The region isn't an option; saving keeps the stored value."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, options={CONF_IS_CN: True})

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert CONF_IS_CN not in result["data_schema"].schema

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SCAN_INTERVAL: 120}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert dict(mock_config_entry.options) == {CONF_SCAN_INTERVAL: 120, CONF_IS_CN: True}


async def test_options_flow_defaults_scan_interval(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Without a stored interval the form defaults to DEFAULT_SCAN_INTERVAL."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    (key,) = result["data_schema"].schema
    assert key.default() == DEFAULT_SCAN_INTERVAL


async def test_abandoned_mfa_flow_releases_the_login_session(
    hass: HomeAssistant, mock_flow_auth: MagicMock, mock_flow_client: MagicMock
) -> None:
    """Closing a flow that waits for an MFA code cancels the pending login."""
    flow_id = await _start_user_flow(hass)
    mock_flow_auth.login.side_effect = GarminMFARequired("ticket")
    result = await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)
    assert result["step_id"] == "mfa"

    hass.config_entries.flow.async_abort(flow_id)
    await hass.async_block_till_done()

    mock_flow_auth.cancel_mfa.assert_awaited_once()


async def test_profile_lookup_uses_the_shared_session(
    hass: HomeAssistant, mock_flow_auth: MagicMock, mock_flow_client: MagicMock
) -> None:
    """The config flow's profile lookup runs on Home Assistant's aiohttp session."""
    from homeassistant.helpers.aiohttp_client import async_get_clientsession

    flow_id = await _start_user_flow(hass)
    with patch("custom_components.garmin_connect.config_flow.GarminClient") as client_cls:
        client_cls.return_value = mock_flow_client
        await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)
    assert client_cls.call_args.kwargs["session"] is async_get_clientsession(hass)

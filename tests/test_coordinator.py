"""Tests for Garmin Connect coordinators, driven through a set-up config entry."""

import asyncio
from datetime import date
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from freezegun.api import FrozenDateTimeFactory
from ha_garmin import GarminAuthError, GarminConnectError
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant.common import MockConfigEntry

from custom_components.garmin_connect.const import (
    CONF_CLIENT_ID,
    CONF_REFRESH_TOKEN,
    CONF_TOKEN,
    DOMAIN,
)
from custom_components.garmin_connect.coordinator import summarize_day

from .conftest import ENTRY_DATA, mock_body_data

_CONNECT_PLUS_ISSUE = "nutrition_connect_plus_required_test_entry_id"
_LIFETIME_ISSUE = "lifetime_totals_hidden_test_entry_id"

_RAW_DAY = {
    "calendarDate": "2026-10-17",
    "averageStressLevel": 42,
    "maxStressLevel": 97,
    "stressDuration": 30000,
    "highStressDuration": 3600,
    "restStressDuration": 24000,
    "bodyBatteryHighestValue": 89,
    "bodyBatteryLowestValue": 8,
    "bodyBatteryChargedValue": 70,
    "bodyBatteryDrainedValue": 81,
    "restingHeartRate": 52,
    "moderateIntensityMinutes": 10,
    "vigorousIntensityMinutes": 25,
    "activeKilocalories": 610,
    "totalSteps": 6909,
}


@pytest.fixture
def client_defaults(mock_client: MagicMock) -> MagicMock:
    """Give the date helpers the init_integration defaults for self-built setups."""
    mock_client.today.return_value = date(2026, 1, 15)
    mock_client.get_daily_summary.return_value = {}
    return mock_client


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set the entry up through Home Assistant, after the test configured the client."""
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)


def _reauth_flows(hass: HomeAssistant) -> list[dict[str, Any]]:
    return [
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["context"]["source"] == SOURCE_REAUTH
    ]


# ── Error mapping and timeouts ───────────────────────────────────────────────


@pytest.mark.parametrize(
    ("side_effect", "error", "translation_key", "placeholders", "reauth"),
    [
        (
            GarminAuthError("expired"),
            ConfigEntryAuthFailed,
            "auth_failed",
            {"error": "expired"},
            True,
        ),
        (
            GarminConnectError("503"),
            UpdateFailed,
            "update_failed",
            {"data": "core", "error": "503"},
            False,
        ),
        (
            TimeoutError,
            UpdateFailed,
            "update_timeout",
            {"data": "core", "seconds": "60"},
            False,
        ),
    ],
)
async def test_refresh_error_mapping(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    side_effect: Exception | type[Exception],
    error: type[Exception],
    translation_key: str,
    placeholders: dict[str, str],
    reauth: bool,
) -> None:
    """Library errors become translated coordinator errors; auth errors start reauth."""
    coordinator = init_integration.runtime_data.core
    mock_client.fetch_core_data.side_effect = side_effect

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert coordinator.last_update_success is False
    exc = coordinator.last_exception
    assert isinstance(exc, error)
    assert exc.translation_key == translation_key
    assert exc.translation_placeholders == placeholders
    assert init_integration.state is ConfigEntryState.LOADED
    assert bool(_reauth_flows(hass)) is reauth


async def test_refresh_timeout_preserves_data_and_recovers(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """A stalled fetch expires without discarding prior data; a later poll recovers."""
    coordinator = init_integration.runtime_data.body
    assert coordinator.data == mock_body_data()
    cancelled = asyncio.Event()

    async def stalled_fetch() -> dict[str, Any]:
        """Simulate a hung cloud fetch and record timeout cancellation."""
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()
        return {}

    mock_client.fetch_body_data.side_effect = stalled_fetch
    # Waiting the real 60 seconds is not an option; the constant is patched where used.
    with patch("custom_components.garmin_connect.coordinator.UPDATE_TIMEOUT", 0.01):
        await asyncio.wait_for(coordinator.async_refresh(), timeout=10)
    assert cancelled.is_set()
    assert coordinator.last_update_success is False
    assert coordinator.last_exception.translation_key == "update_timeout"
    assert coordinator.last_exception.translation_placeholders["data"] == "body"
    assert coordinator.data == mock_body_data()

    mock_client.fetch_body_data.side_effect = None
    mock_client.fetch_body_data.return_value = {"weightKg": 76}
    await coordinator.async_refresh()
    assert coordinator.last_update_success is True
    assert coordinator.data == {"weightKg": 76}


async def test_refresh_external_cancellation_propagates(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Shutdown/unload cancellation must not become a timeout or update failure."""
    coordinator = init_integration.runtime_data.body
    started = asyncio.Event()

    async def hung_fetch() -> dict[str, Any]:
        started.set()
        await asyncio.Event().wait()
        return {}

    mock_client.fetch_body_data.side_effect = hung_fetch
    task = hass.async_create_task(coordinator.async_refresh())
    await asyncio.wait_for(started.wait(), timeout=10)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task
    assert type(coordinator.last_exception) is asyncio.CancelledError


# ── Token persistence ────────────────────────────────────────────────────────


async def test_rotated_tokens_persisted_even_when_fetch_fails(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_auth: MagicMock,
    mock_client: MagicMock,
) -> None:
    """A refresh can rotate the refresh token and the data call still fail.

    The new refresh token must be stored anyway, or the next restart would
    use a dead one and force a reauth.
    """
    coordinator = init_integration.runtime_data.core
    mock_auth.di_token = "new.token"
    mock_auth.di_refresh_token = "new_refresh"
    mock_client.fetch_core_data.side_effect = GarminConnectError("503")

    await coordinator.async_refresh()

    assert coordinator.last_update_success is False
    assert init_integration.data == {
        CONF_TOKEN: "new.token",
        CONF_REFRESH_TOKEN: "new_refresh",
        CONF_CLIENT_ID: ENTRY_DATA[CONF_CLIENT_ID],
    }
    # The rotation is no options change: the entry stays loaded, not reloaded.
    assert init_integration.state is ConfigEntryState.LOADED


async def test_unchanged_tokens_not_rewritten(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """A poll without a token rotation leaves the entry untouched."""
    listener = AsyncMock()
    init_integration.async_on_unload(init_integration.add_update_listener(listener))

    await init_integration.runtime_data.core.async_refresh()
    await hass.async_block_till_done()

    assert init_integration.runtime_data.core.last_update_success is True
    assert init_integration.data == ENTRY_DATA
    listener.assert_not_awaited()


async def test_cleared_tokens_not_persisted(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_auth: MagicMock,
    mock_client: MagicMock,
) -> None:
    """Tokens wiped by a failed login must not overwrite the stored ones."""
    mock_auth.di_token = mock_auth.di_refresh_token = mock_auth.di_client_id = None
    mock_client.fetch_core_data.side_effect = GarminAuthError("bad")

    await init_integration.runtime_data.core.async_refresh()
    await hass.async_block_till_done()

    assert isinstance(init_integration.runtime_data.core.last_exception, ConfigEntryAuthFailed)
    assert init_integration.data == ENTRY_DATA
    assert len(_reauth_flows(hass)) == 1


# ── Per-coordinator fetches ──────────────────────────────────────────────────


async def test_gear_fetch_passes_home_assistant_time_zone(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Alarms are resolved in HA's zone, not the process zone."""
    mock_client.fetch_gear_data.assert_awaited_once_with(timezone=hass.config.time_zone)


async def test_coordinator_names_use_data_domain(init_integration: MockConfigEntry) -> None:
    """Coordinator names carry their data domain, for logs and diagnostics."""
    assert [coord.name for coord in init_integration.runtime_data] == [
        f"garmin_connect_{name}"
        for name in (
            "core",
            "activity",
            "training",
            "body",
            "goals",
            "gear",
            "blood_pressure",
            "menstrual",
            "nutrition",
        )
    ]


# ── Yesterday's final summary ────────────────────────────────────────────────


def test_summarize_day_maps_fields() -> None:
    out = summarize_day(_RAW_DAY, date(2026, 10, 17))
    assert out["yesterdayDate"] == "2026-10-17"
    assert out["yesterdayAverageStressLevel"] == 42
    assert out["yesterdayStressMinutes"] == 500
    assert out["yesterdayHighStressMinutes"] == 60
    assert out["yesterdayBodyBatteryHighest"] == 89
    assert out["yesterdayIntensityMinutes"] == 60
    assert out["yesterdayRestingHeartRate"] == 52


def test_summarize_day_drops_garmin_no_data_stress() -> None:
    out = summarize_day({"averageStressLevel": -1, "maxStressLevel": -2}, date(2026, 10, 17))
    assert out["yesterdayAverageStressLevel"] is None
    assert out["yesterdayMaxStressLevel"] is None
    assert out["yesterdayIntensityMinutes"] is None
    assert out["yesterdayDate"] == "2026-10-17"


class _Watch:
    """Last watch sync the mocked core fetch reports."""

    last_sync = "s1"


@pytest.fixture
def yesterday_client(mock_client: MagicMock) -> MagicMock:
    """Return a client whose core data carries a controllable last sync."""
    _Watch.last_sync = "s1"
    mock_client.today.return_value = date(2026, 10, 18)
    mock_client.fetch_core_data.side_effect = lambda **_: {
        "totalSteps": 1,
        "lastSyncTimestamp": _Watch.last_sync,
    }
    mock_client.get_daily_summary.return_value = dict(_RAW_DAY)
    return mock_client


@pytest.mark.usefixtures("ha_environment", "mock_auth")
async def test_core_skips_yesterday_without_enabled_sensor(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, yesterday_client: MagicMock
) -> None:
    """Disabled yesterday sensors mean no daily summary request."""
    await _setup(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data.core

    await coordinator.async_refresh()
    assert coordinator.data == {"totalSteps": 1, "lastSyncTimestamp": "s1"}
    yesterday_client.get_daily_summary.assert_not_awaited()


@pytest.mark.usefixtures("ha_environment", "mock_auth", "entity_registry_enabled_by_default")
async def test_core_adds_yesterday_and_caches(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, yesterday_client: MagicMock
) -> None:
    """Yesterday's summary is fetched once and kept while day and sync are unchanged."""
    await _setup(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data.core
    assert coordinator.data["totalSteps"] == 1
    assert coordinator.data["yesterdayAverageStressLevel"] == 42
    yesterday_client.get_daily_summary.assert_awaited_once_with(date(2026, 10, 17))

    # Same day, same sync: no second call, values kept.
    await coordinator.async_refresh()
    assert coordinator.data["yesterdayAverageStressLevel"] == 42
    assert yesterday_client.get_daily_summary.await_count == 1

    # A new day fetches the new yesterday.
    yesterday_client.today.return_value = date(2026, 10, 19)
    await coordinator.async_refresh()
    yesterday_client.get_daily_summary.assert_awaited_with(date(2026, 10, 18))
    assert yesterday_client.get_daily_summary.await_count == 2


@pytest.mark.usefixtures("ha_environment", "mock_auth", "entity_registry_enabled_by_default")
async def test_core_refetches_yesterday_on_new_sync(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, yesterday_client: MagicMock
) -> None:
    """A watch upload after midnight can still change yesterday's totals."""
    await _setup(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data.core

    _Watch.last_sync = "s2"  # the watch uploaded (e.g. at 2:25 am)
    yesterday_client.get_daily_summary.return_value = {**_RAW_DAY, "averageStressLevel": 44}
    await coordinator.async_refresh()
    assert coordinator.data["yesterdayAverageStressLevel"] == 44
    assert yesterday_client.get_daily_summary.await_count == 2
    yesterday_client.get_daily_summary.assert_awaited_with(date(2026, 10, 17))


@pytest.mark.usefixtures("ha_environment", "mock_auth", "entity_registry_enabled_by_default")
async def test_core_retries_yesterday_after_empty_summary(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, yesterday_client: MagicMock
) -> None:
    """An empty summary is not cached, so the next poll asks again."""
    yesterday_client.get_daily_summary.return_value = {}
    await _setup(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data.core
    assert "yesterdayAverageStressLevel" not in coordinator.data

    yesterday_client.get_daily_summary.return_value = dict(_RAW_DAY)
    await coordinator.async_refresh()
    assert coordinator.data["yesterdayAverageStressLevel"] == 42
    assert yesterday_client.get_daily_summary.await_count == 2


@pytest.mark.usefixtures("ha_environment", "mock_auth", "entity_registry_enabled_by_default")
async def test_core_drops_old_yesterday_when_new_day_fetch_fails(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, yesterday_client: MagicMock
) -> None:
    """After midnight a failed fetch must not show the day before as yesterday."""
    await _setup(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data.core

    yesterday_client.today.return_value = date(2026, 10, 19)
    yesterday_client.get_daily_summary.side_effect = GarminConnectError("503")
    await coordinator.async_refresh()
    # The core poll itself still succeeds.
    assert coordinator.last_update_success is True
    assert "yesterdayAverageStressLevel" not in coordinator.data

    # The next poll retries.
    yesterday_client.get_daily_summary.side_effect = None
    await coordinator.async_refresh()
    assert coordinator.data["yesterdayAverageStressLevel"] == 42
    yesterday_client.get_daily_summary.assert_awaited_with(date(2026, 10, 18))


@pytest.mark.usefixtures("ha_environment", "mock_auth", "entity_registry_enabled_by_default")
async def test_core_survives_yesterday_failure(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, yesterday_client: MagicMock
) -> None:
    """A failing daily summary never fails the core poll."""
    yesterday_client.get_daily_summary.side_effect = GarminConnectError("503")
    await _setup(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data.core

    assert coordinator.last_update_success is True
    assert coordinator.data == {"totalSteps": 1, "lastSyncTimestamp": "s1"}


async def test_get_day_returns_summary_and_raw(
    init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Any day's summary is returned mapped and raw (used by the services)."""
    mock_client.get_daily_summary.return_value = dict(_RAW_DAY)

    out = await init_integration.runtime_data.core.async_get_day(date(2026, 10, 17))

    mock_client.get_daily_summary.assert_awaited_once_with(date(2026, 10, 17))
    assert out["summary"]["averageStressLevel"] == 42
    assert out["summary"]["date"] == "2026-10-17"
    assert out["summary"]["totalSteps"] == 6909
    assert out["raw"]["maxStressLevel"] == 97


# ── Lifetime totals repair issue ─────────────────────────────────────────────


@pytest.mark.usefixtures("ha_environment", "mock_auth", "client_defaults")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_goals_repair_issue_while_lifetime_totals_hidden(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Hidden lifetime totals raise an issue that goes once they come through."""
    mock_client.fetch_goals_data.return_value = {
        "lifetimeTotals": {},
        "lifetimeTotalsHidden": True,
    }
    await _setup(hass, mock_config_entry)
    mock_client.fetch_goals_data.assert_awaited_once_with(lifetime_totals=True)

    issue = ir.async_get(hass).async_get_issue(DOMAIN, _LIFETIME_ISSUE)
    assert issue is not None
    assert issue.translation_key == "lifetime_totals_hidden"
    assert issue.translation_placeholders == {"title": "test@example.com"}
    assert issue.is_fixable is False

    mock_client.fetch_goals_data.return_value = {
        "lifetimeTotals": {},
        "lifetimeTotalsHidden": False,
    }
    await mock_config_entry.runtime_data.goals.async_refresh()
    assert ir.async_get(hass).async_get_issue(DOMAIN, _LIFETIME_ISSUE) is None


# ── Connect+ (nutrition) repair issue ────────────────────────────────────────


@pytest.fixture
async def empty_nutrition(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    ha_environment: None,
    mock_auth: MagicMock,
) -> MockConfigEntry:
    """Set up with no nutrition data, on day 1.

    Tests mark client_defaults and entity_registry_enabled_by_default, so the
    nutrition sensors exist and are polled.
    """
    freezer.move_to("2026-01-01 20:00:00+00:00")
    mock_client.fetch_nutrition_data.return_value = {}
    await _setup(hass, mock_config_entry)
    return mock_config_entry


async def _poll_on(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, entry: MockConfigEntry, day: int
) -> None:
    freezer.move_to(f"2026-01-{day:02d} 20:00:00+00:00")
    await entry.runtime_data.nutrition.async_refresh()
    await hass.async_block_till_done()


def _connect_plus_issue(hass: HomeAssistant) -> ir.IssueEntry | None:
    return ir.async_get(hass).async_get_issue(DOMAIN, _CONNECT_PLUS_ISSUE)


@pytest.mark.usefixtures("client_defaults", "entity_registry_enabled_by_default")
async def test_connect_plus_issue_after_three_distinct_empty_days(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, empty_nutrition: MockConfigEntry
) -> None:
    """Repeat polls on one day count once; the issue fires on the third empty day only."""
    for _ in range(4):
        await _poll_on(hass, freezer, empty_nutrition, 1)
    await _poll_on(hass, freezer, empty_nutrition, 2)
    assert _connect_plus_issue(hass) is None

    await _poll_on(hass, freezer, empty_nutrition, 3)
    issue = _connect_plus_issue(hass)
    assert issue is not None
    assert issue.translation_key == "connect_plus_required"
    assert issue.is_fixable is False
    assert issue.translation_placeholders == {"title": "test@example.com"}

    # A 4th empty day must not raise the same issue again once dismissed.
    ir.async_delete_issue(hass, DOMAIN, _CONNECT_PLUS_ISSUE)
    await _poll_on(hass, freezer, empty_nutrition, 4)
    assert _connect_plus_issue(hass) is None


@pytest.mark.usefixtures("client_defaults", "entity_registry_enabled_by_default")
async def test_connect_plus_issue_cleared_once_data_returns(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    empty_nutrition: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Real data clears the issue, and later empty days never raise it again."""
    for day in (2, 3):
        await _poll_on(hass, freezer, empty_nutrition, day)
    assert _connect_plus_issue(hass) is not None

    mock_client.fetch_nutrition_data.return_value = {"nutritionConsumedCalories": 2000}
    await _poll_on(hass, freezer, empty_nutrition, 3)
    assert _connect_plus_issue(hass) is None

    mock_client.fetch_nutrition_data.return_value = {}
    for day in (4, 5, 6, 7):
        await _poll_on(hass, freezer, empty_nutrition, day)
    assert _connect_plus_issue(hass) is None


@pytest.mark.usefixtures("ha_environment", "mock_auth", "client_defaults")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_connect_plus_issue_never_fires_once_real_data_seen(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Once any poll returned real data, empty days are just days without logging."""
    freezer.move_to("2026-01-01 08:00:00+00:00")
    await _setup(hass, mock_config_entry)
    assert mock_config_entry.runtime_data.nutrition.data

    mock_client.fetch_nutrition_data.return_value = {}
    for day in (1, 2, 3, 4):
        await _poll_on(hass, freezer, mock_config_entry, day)
    assert _connect_plus_issue(hass) is None


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_translated_errors_render_their_cause(hass: HomeAssistant) -> None:
    """With the integration's translations loaded, the logged text names the cause."""
    from homeassistant.helpers.translation import async_load_integrations

    # Messages are looked up for loaded components only, as at runtime.
    hass.config.components.add(DOMAIN)
    await async_load_integrations(hass, {DOMAIN})
    auth = ConfigEntryAuthFailed(
        translation_domain=DOMAIN,
        translation_key="auth_failed",
        translation_placeholders={"error": "DI token refresh failed: HTTP 400"},
    )
    assert str(auth) == (
        "Authentication with Garmin Connect failed: DI token refresh failed: HTTP 400"
    )
    failed = UpdateFailed(
        translation_domain=DOMAIN,
        translation_key="update_failed",
        translation_placeholders={"data": "core", "error": "503"},
    )
    assert str(failed) == "Error fetching Garmin Connect core data: 503"

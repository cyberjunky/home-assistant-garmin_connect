"""Tests for Garmin Connect integration setup, unload and migration."""

import asyncio
from datetime import date, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from ha_garmin import GarminAuthError, GarminConnectError
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.loader import async_get_integration
from pytest_homeassistant.common import MockConfigEntry

import custom_components.garmin_connect as garmin_connect
from custom_components.garmin_connect.const import (
    CONF_CLIENT_ID,
    CONF_IS_CN,
    CONF_REFRESH_TOKEN,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from custom_components.garmin_connect.coordinator import (
    ActivityCoordinator,
    BloodPressureCoordinator,
    BodyCoordinator,
    CoreCoordinator,
    GarminConnectCoordinators,
    GearCoordinator,
    GoalsCoordinator,
    MenstrualCoordinator,
    NutritionCoordinator,
    TrainingCoordinator,
)
from custom_components.garmin_connect.services import (
    SERVICE_ADD_BLOOD_PRESSURE,
    SERVICE_ADD_BODY_COMPOSITION,
    SERVICE_SET_ACTIVE_GEAR,
)

from .conftest import ENTRY_DATA

pytestmark = pytest.mark.usefixtures("ha_environment", "mock_auth", "client_defaults")

_CONNECT_PLUS_ISSUE = "nutrition_connect_plus_required_test_entry_id"
_LIFETIME_ISSUE = "lifetime_totals_hidden_test_entry_id"


async def _setup(hass: HomeAssistant, entry: MockConfigEntry, *, wait: bool = True) -> None:
    """Add the entry (unless added already) and set it up through Home Assistant."""
    if hass.config_entries.async_get_entry(entry.entry_id) is None:
        entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    if wait:
        await hass.async_block_till_done(wait_background_tasks=True)


@pytest.fixture
def client_defaults(mock_client: MagicMock) -> MagicMock:
    """Give the date helpers the init_integration defaults for self-built setups."""
    mock_client.today.return_value = date(2026, 1, 15)
    mock_client.get_daily_summary.return_value = {}
    return mock_client


def _reauth_flows(hass: HomeAssistant) -> list[dict[str, Any]]:
    return [
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["context"]["source"] == SOURCE_REAUTH
    ]


def _create_issue(hass: HomeAssistant, issue_id: str) -> None:
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="lifetime_totals_hidden",
    )


# ── Setup, unload and removal ────────────────────────────────────────────────


async def test_setup_and_unload(hass: HomeAssistant, init_integration: MockConfigEntry) -> None:
    """The entry loads with all nine coordinators; unloading keeps the services."""
    entry = init_integration
    assert entry.state is ConfigEntryState.LOADED
    assert entry.version == 2
    assert not _reauth_flows(hass)

    coordinators = entry.runtime_data
    assert isinstance(coordinators, GarminConnectCoordinators)
    assert [type(coord) for coord in coordinators] == [
        CoreCoordinator,
        ActivityCoordinator,
        TrainingCoordinator,
        BodyCoordinator,
        GoalsCoordinator,
        GearCoordinator,
        BloodPressureCoordinator,
        MenstrualCoordinator,
        NutritionCoordinator,
    ]
    assert coordinators.is_cn is False

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
    # Services are registered once in async_setup and serve every entry.
    for service in (
        SERVICE_SET_ACTIVE_GEAR,
        SERVICE_ADD_BODY_COMPOSITION,
        SERVICE_ADD_BLOOD_PRESSURE,
    ):
        assert hass.services.has_service(DOMAIN, service)


async def test_setup_serves_and_registers_route_card(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """The card folder is served and the card auto-loaded, version-busted."""
    integration = await async_get_integration(hass, DOMAIN)

    (configs,) = hass.http.async_register_static_paths.await_args.args
    assert len(configs) == 1
    assert configs[0].url_path == "/garmin_connect"
    assert configs[0].path.endswith("custom_components/garmin_connect/www")
    # ha_environment patches add_extra_js_url where the integration uses it.
    garmin_connect.add_extra_js_url.assert_called_once_with(
        hass, f"/garmin_connect/garmin-polyline-card.js?v={integration.version}"
    )


@pytest.mark.parametrize("is_cn", [False, True])
async def test_setup_builds_client_from_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_auth: MagicMock,
    mock_client: MagicMock,
    is_cn: bool,
) -> None:
    """Stored tokens, the region and HA's time zone reach the ha-garmin client."""
    await hass.config.async_set_time_zone("Europe/Istanbul")
    mock_auth.di_token = mock_auth.di_refresh_token = mock_auth.di_client_id = None
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, options={CONF_IS_CN: is_cn})

    await _setup(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_auth.di_token == ENTRY_DATA[CONF_TOKEN]
    assert mock_auth.di_refresh_token == ENTRY_DATA[CONF_REFRESH_TOKEN]
    assert mock_auth.di_client_id == ENTRY_DATA[CONF_CLIENT_ID]
    # The library classes are patched where the integration uses them.
    garmin_connect.GarminAuth.assert_called_once_with(is_cn=is_cn)
    assert garmin_connect.GarminClient.call_args.kwargs == {
        "is_cn": is_cn,
        "timezone": "Europe/Istanbul",
        # The data API runs on Home Assistant's shared aiohttp session.
        "session": async_get_clientsession(hass),
    }
    # The region the client was built for is kept for reload detection.
    assert mock_config_entry.runtime_data.is_cn is is_cn


@pytest.mark.parametrize(
    ("side_effect", "state", "reauth"),
    [
        (GarminConnectError("down"), ConfigEntryState.SETUP_RETRY, False),
        (TimeoutError, ConfigEntryState.SETUP_RETRY, False),
        (GarminAuthError("expired"), ConfigEntryState.SETUP_ERROR, True),
    ],
)
async def test_setup_core_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    side_effect: Exception | type[Exception],
    state: ConfigEntryState,
    reauth: bool,
) -> None:
    """A failing core refresh retries setup; an auth failure asks for reauth."""
    mock_client.fetch_core_data.side_effect = side_effect

    await _setup(hass, mock_config_entry)

    assert mock_config_entry.state is state
    assert bool(_reauth_flows(hass)) is reauth
    mock_client.fetch_activity_data.assert_not_awaited()


async def test_setup_requires_token(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """An entry without DI tokens fails setup and starts a reauth flow."""
    entry = MockConfigEntry(
        domain=DOMAIN, title="test@example.com", data={}, unique_id="123", version=2
    )

    await _setup(hass, entry)

    assert entry.state is ConfigEntryState.SETUP_ERROR
    (flow,) = _reauth_flows(hass)
    assert flow["context"]["entry_id"] == entry.entry_id
    mock_client.fetch_core_data.assert_not_awaited()


async def test_optional_refresh_does_not_block_startup(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Setup returns while optional refreshes are still pending."""
    started = asyncio.Event()
    release = asyncio.Event()
    finished = asyncio.Event()
    registry = er.async_get(hass)

    async def slow_fetch() -> dict[str, Any]:
        """Keep optional work pending until the test releases it."""
        # Optional refreshes only start once the entities (and listeners) exist.
        assert registry.async_get_entity_id("sensor", DOMAIN, "test_entry_id_trainingReadiness")
        started.set()
        await release.wait()
        finished.set()
        return {}

    mock_client.fetch_training_data.side_effect = slow_fetch

    await asyncio.wait_for(_setup(hass, mock_config_entry, wait=False), timeout=10)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    await asyncio.wait_for(started.wait(), timeout=10)
    # HA's startup barrier deliberately excludes entry background tasks.
    await asyncio.wait_for(hass.async_block_till_done(), timeout=10)
    assert not finished.is_set()

    release.set()
    await asyncio.wait_for(finished.wait(), timeout=10)


async def test_setup_skips_coordinators_without_listeners(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """No enabled entity, no fetch: menstrual/nutrition stay idle, their peers refresh."""
    mock_client.fetch_menstrual_data.assert_not_awaited()
    mock_client.fetch_nutrition_data.assert_not_awaited()
    mock_client.fetch_training_data.assert_awaited_once()
    # No opt-in core sensor is enabled, so core only ran its first refresh.
    mock_client.fetch_core_data.assert_awaited_once_with(latest_heart_rate=False)
    mock_client.get_daily_summary.assert_not_awaited()
    mock_client.fetch_goals_data.assert_awaited_once_with(lifetime_totals=False)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_setup_refreshes_core_for_opt_in_sensors(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Core's first refresh ran without sensor contexts, so it is repeated once."""
    assert mock_client.fetch_core_data.await_count == 2
    mock_client.fetch_core_data.assert_awaited_with(latest_heart_rate=True)
    mock_client.fetch_menstrual_data.assert_awaited_once()
    mock_client.fetch_nutrition_data.assert_awaited_once()
    mock_client.fetch_goals_data.assert_awaited_once_with(lifetime_totals=True)


async def test_setup_clears_issues_of_unused_features(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Disabled nutrition/lifetime sensors are never polled, so setup drops their issues."""
    _create_issue(hass, _CONNECT_PLUS_ISSUE)
    _create_issue(hass, _LIFETIME_ISSUE)

    await _setup(hass, mock_config_entry)

    issues = ir.async_get(hass)
    assert issues.async_get_issue(DOMAIN, _CONNECT_PLUS_ISSUE) is None
    assert issues.async_get_issue(DOMAIN, _LIFETIME_ISSUE) is None


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_setup_keeps_issues_of_used_features(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Polled coordinators manage their own issues."""
    _create_issue(hass, _CONNECT_PLUS_ISSUE)
    _create_issue(hass, _LIFETIME_ISSUE)
    # Still no nutrition data, lifetime totals still hidden.
    mock_client.fetch_nutrition_data.return_value = {}
    mock_client.fetch_goals_data.return_value = {"lifetimeTotalsHidden": True}

    await _setup(hass, mock_config_entry)

    issues = ir.async_get(hass)
    assert issues.async_get_issue(DOMAIN, _CONNECT_PLUS_ISSUE) is not None
    assert issues.async_get_issue(DOMAIN, _LIFETIME_ISSUE) is not None


async def test_remove_entry_removes_its_repair_issues(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Removing the entry deletes its repair issues."""
    _create_issue(hass, _CONNECT_PLUS_ISSUE)
    _create_issue(hass, _LIFETIME_ISSUE)

    await hass.config_entries.async_remove(init_integration.entry_id)
    await hass.async_block_till_done()

    issues = ir.async_get(hass)
    assert issues.async_get_issue(DOMAIN, _CONNECT_PLUS_ISSUE) is None
    assert issues.async_get_issue(DOMAIN, _LIFETIME_ISSUE) is None


# ── Options listener ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("options", "seconds"),
    [
        ({CONF_SCAN_INTERVAL: 120}, 120),
        # Region changes come from reauth/reconfigure, which reload on their own.
        ({CONF_IS_CN: True}, DEFAULT_SCAN_INTERVAL),
    ],
)
async def test_options_update_without_reload(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    options: dict[str, Any],
    seconds: int,
) -> None:
    """Changed options are pushed to every coordinator; the entry is never reloaded."""
    coordinators = init_integration.runtime_data
    for coord in coordinators:
        coord.update_interval = timedelta(seconds=1)

    hass.config_entries.async_update_entry(init_integration, options=options)
    await hass.async_block_till_done()

    assert init_integration.state is ConfigEntryState.LOADED
    # A reload would have built new coordinators and a new GarminAuth.
    assert init_integration.runtime_data is coordinators
    assert coordinators.is_cn is False
    garmin_connect.GarminAuth.assert_called_once()
    for coord in coordinators:
        assert coord.update_interval == timedelta(seconds=seconds)


# ── Migration v1 -> v2 ────────────────────────────────────────────────────────


async def test_migrate_v1_to_v2(
    hass: HomeAssistant, mock_client: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """V1 entities keep their entity_ids under v2 unique_ids and reauth is requested."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="user@example.com",
        # v1 stored the garth session under "token", without a refresh token.
        data={"id": "user@example.com", "username": "user@example.com", "token": "garth"},
        unique_id="user@example.com",
        entry_id="new_entry_id",
        version=1,
    )
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    v1_unique_ids = {
        "unchanged": "user@example.com_totalSteps",
        "renamed": "user@example.com_sleepingSeconds",
        "dropped": "user@example.com_netCalorieGoal",
        "foreign": "other_prefix_totalSteps",
        # Two v1 keys that both map to stressMinutes: the second one conflicts.
        "conflict_a": "user@example.com_totalStressDuration",
        "conflict_b": "user@example.com_stressDuration",
    }
    entity_ids = {
        name: registry.async_get_or_create(
            "sensor", DOMAIN, unique_id, config_entry=entry, suggested_object_id=name
        ).entity_id
        for name, unique_id in v1_unique_ids.items()
    }

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 2
    # The garth session is no DI token set: setup fails cleanly until the reauth,
    # not with a KeyError on the missing refresh token.
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert "KeyError" not in caplog.text
    assert "Error setting up entry" not in caplog.text
    (flow,) = _reauth_flows(hass)
    assert flow["context"]["entry_id"] == entry.entry_id
    mock_client.fetch_core_data.assert_not_awaited()

    def unique_id(name: str) -> str:
        reg_entry = registry.async_get(entity_ids[name])
        assert reg_entry is not None
        return reg_entry.unique_id

    assert unique_id("unchanged") == "new_entry_id_totalSteps"
    assert unique_id("renamed") == "new_entry_id_sleepingMinutes"
    assert unique_id("dropped") == "user@example.com_netCalorieGoal"
    assert unique_id("foreign") == "other_prefix_totalSteps"
    # The conflict is logged, not fatal: one entity wins the new unique_id.
    assert {unique_id("conflict_a"), unique_id("conflict_b")} in (
        {"new_entry_id_stressMinutes", v1_unique_ids["conflict_b"]},
        {"new_entry_id_stressMinutes", v1_unique_ids["conflict_a"]},
    )


@pytest.mark.parametrize(
    ("entry_unique_id", "entity_unique_id"),
    [
        # The prefix already is the entry_id: nothing to rewrite.
        ("new_entry_id", "new_entry_id_totalSteps"),
        # No v1 unique_id: entities are left alone.
        (None, "user@example.com_totalSteps"),
    ],
)
async def test_migrate_v1_without_rewrite(
    hass: HomeAssistant, entry_unique_id: str | None, entity_unique_id: str
) -> None:
    """Entities that need no new unique_id are kept; the entry still moves to v2."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="user@example.com",
        data={},
        unique_id=entry_unique_id,
        entry_id="new_entry_id",
        version=1,
    )
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    entity_id = registry.async_get_or_create(
        "sensor", DOMAIN, entity_unique_id, config_entry=entry
    ).entity_id

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 2
    assert len(_reauth_flows(hass)) == 1
    reg_entry = registry.async_get(entity_id)
    assert reg_entry is not None
    assert reg_entry.unique_id == entity_unique_id


async def test_v2_entry_is_not_migrated(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """A v2 entry keeps its entity unique_ids and needs no reauth."""
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("sensor", DOMAIN, "test_entry_id_totalSteps")
    assert entity_id is not None
    assert init_integration.version == 2
    assert not _reauth_flows(hass)


async def test_rotated_tokens_persisted_after_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_auth: MagicMock,
    mock_client: MagicMock,
) -> None:
    """A token refresh during the first poll is written back to the entry."""

    async def rotate(**_: Any) -> dict[str, Any]:
        mock_auth.di_token = "rotated.token"
        mock_auth.di_refresh_token = "rotated_refresh"
        return {"totalSteps": 1}

    mock_client.fetch_core_data = AsyncMock(side_effect=rotate)

    await _setup(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.data == {
        **ENTRY_DATA,
        CONF_TOKEN: "rotated.token",
        CONF_REFRESH_TOKEN: "rotated_refresh",
    }

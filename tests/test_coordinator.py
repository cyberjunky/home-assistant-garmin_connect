"""Tests for Garmin Connect coordinators."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from ha_garmin import GarminAuthError, GarminConnectError
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.garmin_connect.const import (
    CONF_CLIENT_ID,
    CONF_REFRESH_TOKEN,
    CONF_TOKEN,
)
from custom_components.garmin_connect.coordinator import (
    BodyCoordinator,
    CoreCoordinator,
    GearCoordinator,
    NutritionCoordinator,
)

from .conftest import ENTRY_DATA

_DAY_1 = date(2026, 1, 1)
_DAY_2 = date(2026, 1, 2)
_DAY_3 = date(2026, 1, 3)
_DAY_4 = date(2026, 1, 4)


def _make_coordinator(client: AsyncMock, *, nutrition_enabled: bool = True) -> NutritionCoordinator:
    """Build a NutritionCoordinator with mocked hass/entry/auth.

    `nutrition_enabled` stubs out the entity-registry lookup so tests don't need a
    real registry - defaults to True (opted in) since most tests exercise the
    empty-day/threshold logic that only runs once a user has enabled the feature.
    """
    hass = MagicMock()
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.title = "test@example.com"
    entry.options = {}
    entry.data = {}
    auth = MagicMock()
    coordinator = NutritionCoordinator(hass, entry, client, auth)
    coordinator._update_tokens_if_changed = MagicMock()
    coordinator._has_enabled_nutrition_entity = MagicMock(return_value=nutrition_enabled)
    return coordinator


def _make_client(*, empty: bool) -> AsyncMock:
    client = AsyncMock()
    client.fetch_nutrition_data = AsyncMock(return_value={} if empty else {"calories": 2000})
    return client


def _mock_today(day: date):
    patcher = patch("custom_components.garmin_connect.coordinator.dt_util.now")
    mock_now = patcher.start()
    mock_now.return_value.date.return_value = day
    return patcher


async def test_same_day_repeat_polls_do_not_stack() -> None:
    """Multiple empty polls within the same calendar day only count once."""
    coordinator = _make_coordinator(_make_client(empty=True))
    with patch("custom_components.garmin_connect.coordinator.ir") as mock_ir:
        day_patch = _mock_today(_DAY_1)
        try:
            for _ in range(5):
                await coordinator._async_update_data()
        finally:
            day_patch.stop()

        # 5 polls, all on day 1 -> only 1 distinct empty day recorded, well under threshold.
        assert coordinator._empty_days == 1
        mock_ir.async_create_issue.assert_not_called()


async def test_issue_created_after_three_distinct_empty_days() -> None:
    """The issue fires only once 3 distinct calendar days have been empty."""
    coordinator = _make_coordinator(_make_client(empty=True))
    with patch("custom_components.garmin_connect.coordinator.ir") as mock_ir:
        for day in (_DAY_1, _DAY_2):
            day_patch = _mock_today(day)
            try:
                await coordinator._async_update_data()
            finally:
                day_patch.stop()
        mock_ir.async_create_issue.assert_not_called()

        day_patch = _mock_today(_DAY_3)
        try:
            await coordinator._async_update_data()
        finally:
            day_patch.stop()

        mock_ir.async_create_issue.assert_called_once()
        _, kwargs = mock_ir.async_create_issue.call_args
        assert kwargs["translation_key"] == "connect_plus_required"
        assert kwargs["is_fixable"] is False
        assert kwargs["translation_placeholders"] == {"title": "test@example.com"}

        # A 4th empty day must not re-raise the same issue again.
        day_patch = _mock_today(_DAY_4)
        try:
            await coordinator._async_update_data()
        finally:
            day_patch.stop()
        mock_ir.async_create_issue.assert_called_once()


async def test_issue_never_fires_once_real_data_seen() -> None:
    """Once any poll returns real data, later empty days must never raise the issue."""
    coordinator = _make_coordinator(_make_client(empty=False))
    with patch("custom_components.garmin_connect.coordinator.ir") as mock_ir:
        await coordinator._async_update_data()
        assert coordinator._ever_had_data is True

        coordinator.client.fetch_nutrition_data = AsyncMock(return_value={})
        for day in (_DAY_1, _DAY_2, _DAY_3, _DAY_4):
            day_patch = _mock_today(day)
            try:
                await coordinator._async_update_data()
            finally:
                day_patch.stop()

        mock_ir.async_create_issue.assert_not_called()


async def test_issue_cleared_once_data_returns() -> None:
    """The repair issue is deleted as soon as nutrition data is non-empty again."""
    coordinator = _make_coordinator(_make_client(empty=True))
    with patch("custom_components.garmin_connect.coordinator.ir") as mock_ir:
        for day in (_DAY_1, _DAY_2, _DAY_3):
            day_patch = _mock_today(day)
            try:
                await coordinator._async_update_data()
            finally:
                day_patch.stop()
        mock_ir.async_create_issue.assert_called_once()

        coordinator.client.fetch_nutrition_data = AsyncMock(return_value={"calories": 2000})
        await coordinator._async_update_data()

        mock_ir.async_delete_issue.assert_called_once()
        assert coordinator._empty_days == 0
        assert coordinator._ever_had_data is True


async def test_no_issue_when_nutrition_never_enabled() -> None:
    """Users who never enable the (disabled-by-default) nutrition sensors are never nagged.

    NutritionCoordinator polls unconditionally regardless of entity enablement, so most
    installs have no Connect+ and would hit the empty-day threshold - this must not
    surface a repair issue unless the user actually opted into the feature.
    """
    coordinator = _make_coordinator(_make_client(empty=True), nutrition_enabled=False)
    with patch("custom_components.garmin_connect.coordinator.ir") as mock_ir:
        for day in (_DAY_1, _DAY_2, _DAY_3, _DAY_4, date(2026, 1, 5)):
            day_patch = _mock_today(day)
            try:
                await coordinator._async_update_data()
            finally:
                day_patch.stop()

        mock_ir.async_create_issue.assert_not_called()
        assert coordinator._empty_days == 0


async def test_issue_starts_fresh_debounce_after_enabling() -> None:
    """Enabling nutrition sensors after a long silent gap starts a clean 3-day window.

    A streak that accumulated while the feature was disabled must not immediately
    fire on the first poll after the user opts in.
    """
    coordinator = _make_coordinator(_make_client(empty=True), nutrition_enabled=False)
    with patch("custom_components.garmin_connect.coordinator.ir") as mock_ir:
        for day in (_DAY_1, _DAY_2, _DAY_3, _DAY_4):
            day_patch = _mock_today(day)
            try:
                await coordinator._async_update_data()
            finally:
                day_patch.stop()
        mock_ir.async_create_issue.assert_not_called()

        coordinator._has_enabled_nutrition_entity = MagicMock(return_value=True)
        day_5 = date(2026, 1, 5)
        day_patch = _mock_today(day_5)
        try:
            await coordinator._async_update_data()
        finally:
            day_patch.stop()
        assert coordinator._empty_days == 1
        mock_ir.async_create_issue.assert_not_called()

        for day in (date(2026, 1, 6), date(2026, 1, 7)):
            day_patch = _mock_today(day)
            try:
                await coordinator._async_update_data()
            finally:
                day_patch.stop()

        mock_ir.async_create_issue.assert_called_once()


# ── Base coordinator: error mapping and token persistence ────────────────────


def _make_base(client: AsyncMock, *, auth_tokens: dict | None = None) -> CoreCoordinator:
    hass = MagicMock()
    hass.config.time_zone = "Europe/Amsterdam"
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.options = {}
    entry.data = dict(ENTRY_DATA)
    auth = MagicMock()
    for key, value in (auth_tokens or ENTRY_DATA).items():
        setattr(
            auth,
            {"token": "di_token", "refresh_token": "di_refresh_token", "client_id": "di_client_id"}[
                key
            ],
            value,
        )
    return CoreCoordinator(hass, entry, client, auth)


async def test_auth_error_maps_to_config_entry_auth_failed() -> None:
    client = AsyncMock()
    client.fetch_core_data = AsyncMock(side_effect=GarminAuthError("expired"))
    coordinator = _make_base(client)
    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


async def test_connect_error_maps_to_update_failed() -> None:
    client = AsyncMock()
    client.fetch_core_data = AsyncMock(side_effect=GarminConnectError("503"))
    coordinator = _make_base(client)
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_rotated_tokens_persisted_even_when_fetch_fails() -> None:
    """A refresh can rotate the refresh token and the data call still fail.

    The new refresh token must be stored anyway, or the next restart would
    use a dead one and force a reauth.
    """
    client = AsyncMock()
    client.fetch_core_data = AsyncMock(side_effect=GarminConnectError("503"))
    rotated = {
        CONF_TOKEN: "new.token",
        CONF_REFRESH_TOKEN: "new_refresh",
        CONF_CLIENT_ID: ENTRY_DATA[CONF_CLIENT_ID],
    }
    coordinator = _make_base(client, auth_tokens=rotated)

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()

    coordinator.hass.config_entries.async_update_entry.assert_called_once()
    _, kwargs = coordinator.hass.config_entries.async_update_entry.call_args
    assert kwargs["data"][CONF_TOKEN] == "new.token"
    assert kwargs["data"][CONF_REFRESH_TOKEN] == "new_refresh"


async def test_unchanged_tokens_not_rewritten() -> None:
    client = AsyncMock()
    client.fetch_core_data = AsyncMock(return_value={"totalSteps": 1})
    coordinator = _make_base(client)

    assert await coordinator._async_update_data() == {"totalSteps": 1}
    coordinator.hass.config_entries.async_update_entry.assert_not_called()


async def test_cleared_tokens_not_persisted() -> None:
    """Tokens wiped by a failed login must not overwrite the stored ones."""
    client = AsyncMock()
    client.fetch_core_data = AsyncMock(side_effect=GarminAuthError("bad"))
    coordinator = _make_base(
        client, auth_tokens={CONF_TOKEN: None, CONF_REFRESH_TOKEN: None, CONF_CLIENT_ID: None}
    )
    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()
    coordinator.hass.config_entries.async_update_entry.assert_not_called()


async def test_gear_fetch_passes_home_assistant_time_zone() -> None:
    client = AsyncMock()
    client.fetch_gear_data = AsyncMock(return_value={})
    coordinator = _make_base(client)
    gear = GearCoordinator(coordinator.hass, coordinator.config_entry, client, coordinator.auth)
    await gear._async_update_data()
    client.fetch_gear_data.assert_awaited_once_with(timezone="Europe/Amsterdam")


def test_coordinator_names_use_data_domain() -> None:
    client = AsyncMock()
    coordinator = _make_base(client)
    body = BodyCoordinator(coordinator.hass, coordinator.config_entry, client, coordinator.auth)
    assert coordinator.name == "garmin_connect_core"
    assert body.name == "garmin_connect_body"

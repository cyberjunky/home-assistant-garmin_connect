"""Tests for Garmin Connect diagnostics."""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from .conftest import mock_activity_data

pytestmark = pytest.mark.usefixtures("enable_custom_integrations", "http_environment")

# Every value below that diagnostics must hide.
_PROFILE = {
    "displayName": "ron",
    "fullName": "Ron Runner",
    "userName": "ron@example.com",
    "email": "ron@example.com",
    "profileImageUrlSmall": "https://example.com/s.png",
    "profileImageUrlMedium": "https://example.com/m.png",
    "profileImageUrlLarge": "https://example.com/l.png",
}
_ACTIVITY = {
    "activityId": 12345,
    "activityName": "Ride",
    "startTime": datetime(2026, 1, 14, 7, 0, tzinfo=UTC),
    "polyline": [{"lat": 52.1, "lon": 5.1}],
    "startLatitude": 52.1,
    "startLongitude": 5.1,
    "endLatitude": 52.2,
    "endLongitude": 5.2,
    "locationName": "Home town",
}


@pytest.fixture
async def http_environment(hass: HomeAssistant) -> AsyncGenerator[None]:
    """Load the real http component (the diagnostics API needs it); stub only frontend.

    hass_frontend is not installed in the test environment, so frontend is
    marked loaded and the one call the integration makes into it is stubbed.
    """
    hass.config.components.add("frontend")
    assert await async_setup_component(hass, "http", {})
    with patch("custom_components.garmin_connect.add_extra_js_url"):
        yield


@pytest.fixture
async def diagnostics_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_auth: MagicMock,
    mock_client: MagicMock,
) -> MockConfigEntry:
    """Set up an entry whose data holds every kind of value diagnostics redacts."""
    mock_client.fetch_core_data.return_value = {"totalSteps": 10000, **_PROFILE}
    mock_client.fetch_activity_data.return_value = {
        **mock_activity_data(),
        "lastActivity": _ACTIVITY,
        "lastActivities": [_ACTIVITY],
    }
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return mock_config_entry


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    diagnostics_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Coordinator payloads are included, minus tokens, identity, notes and locations."""
    assert await get_diagnostics_for_config_entry(hass, hass_client, diagnostics_entry) == snapshot


async def test_diagnostics_without_update_interval(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    diagnostics_entry: MockConfigEntry,
) -> None:
    """A coordinator that is not polled reports no update interval."""
    diagnostics_entry.runtime_data.core.update_interval = None

    result = await get_diagnostics_for_config_entry(hass, hass_client, diagnostics_entry)

    assert result["coordinators"]["core"]["update_interval_seconds"] is None

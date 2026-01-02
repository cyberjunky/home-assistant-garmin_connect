"""Tests for Garmin Connect constants.

These tests use mocking to avoid requiring the full Home Assistant stack.
"""

import sys
from unittest.mock import MagicMock

# Mock homeassistant modules before importing const
sys.modules["homeassistant"] = MagicMock()
sys.modules["homeassistant.config_entries"] = MagicMock()
sys.modules["homeassistant.core"] = MagicMock()
sys.modules["homeassistant.const"] = MagicMock()
sys.modules["homeassistant.helpers"] = MagicMock()
sys.modules["homeassistant.helpers.device_registry"] = MagicMock()
sys.modules["homeassistant.helpers.update_coordinator"] = MagicMock()
sys.modules["homeassistant.exceptions"] = MagicMock()
sys.modules["garminconnect"] = MagicMock()
sys.modules["garth"] = MagicMock()
sys.modules["garth.exc"] = MagicMock()

from custom_components.garmin_connect.const import (  # noqa: E402
    DAY_TO_NUMBER,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    GEAR_ICONS,
    LEVEL_POINTS,
    Gear,
    ServiceSetting,
)


def test_domain():
    """Test domain constant."""
    assert DOMAIN == "garmin_connect"


def test_default_update_interval():
    """Test default update interval."""
    assert DEFAULT_UPDATE_INTERVAL.total_seconds() == 300  # 5 minutes


def test_day_to_number():
    """Test day to number mapping."""
    assert DAY_TO_NUMBER["Mo"] == 1
    assert DAY_TO_NUMBER["Su"] == 7
    assert len(DAY_TO_NUMBER) >= 7  # Has aliases for days


def test_level_points():
    """Test level points mapping."""
    assert 1 in LEVEL_POINTS
    assert LEVEL_POINTS[1] == 0
    assert len(LEVEL_POINTS) > 0


def test_gear_icons():
    """Test gear icons mapping."""
    assert "Shoes" in GEAR_ICONS
    assert "Bike" in GEAR_ICONS
    assert "Other" in GEAR_ICONS


def test_service_setting():
    """Test ServiceSetting class."""
    assert ServiceSetting.DEFAULT == "set as default"
    assert ServiceSetting.UNSET_DEFAULT == "unset default"


def test_gear_class():
    """Test Gear class."""
    assert Gear.UUID == "uuid"
    assert Gear.USERPROFILE_ID == "userProfileId"

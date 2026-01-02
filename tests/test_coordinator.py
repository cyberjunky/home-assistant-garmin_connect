"""Tests for Garmin Connect coordinator."""



from custom_components.garmin_connect.coordinator import (
    calculate_next_active_alarms,
)


async def test_calculate_next_active_alarms_empty():
    """Test calculate_next_active_alarms with empty alarms."""
    result = calculate_next_active_alarms([], "UTC")
    assert result == []


async def test_calculate_next_active_alarms_none():
    """Test calculate_next_active_alarms with None."""
    result = calculate_next_active_alarms(None, "UTC")
    assert result == []


async def test_calculate_next_active_alarms_off():
    """Test calculate_next_active_alarms with alarm mode OFF."""
    alarms = [{"alarmMode": "OFF", "alarmDays": ["MONDAY"], "alarmTime": 480}]
    result = calculate_next_active_alarms(alarms, "UTC")
    assert result == []


async def test_calculate_next_active_alarms_once():
    """Test calculate_next_active_alarms with ONCE alarm."""
    alarms = [{"alarmMode": "ON", "alarmDays": ["ONCE"], "alarmTime": 480}]
    result = calculate_next_active_alarms(alarms, "UTC")
    assert result is not None
    assert len(result) == 1

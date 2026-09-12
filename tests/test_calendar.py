"""Tests for Garmin Connect calendar platform."""

from datetime import UTC, date, datetime
from unittest.mock import MagicMock

from custom_components.garmin_connect.calendar import (
    GarminScheduledWorkoutsCalendar,
    _event_from_workout,
)

from .conftest import mock_activity_data


def test_event_from_workout_builds_all_day_event() -> None:
    """A workout item becomes an all-day CalendarEvent (end is exclusive)."""
    workout = {
        "id": 1774018003,
        "date": "2026-09-12",
        "title": "Benchmark Run",
        "sportTypeKey": "running",
    }
    event = _event_from_workout(workout)
    assert event is not None
    assert event.start == date(2026, 9, 12)
    assert event.end == date(2026, 9, 13)
    assert event.summary == "Benchmark Run"
    assert event.description == "running"
    assert event.uid == "1774018003"


def test_event_from_workout_missing_title_falls_back() -> None:
    """A workout with no title still produces an event with a generic summary."""
    event = _event_from_workout({"date": "2026-09-12"})
    assert event is not None
    assert event.summary == "Scheduled workout"
    assert event.uid is None


def test_event_from_workout_returns_none_without_date() -> None:
    assert _event_from_workout({"title": "No Date"}) is None


def test_event_from_workout_returns_none_on_bad_date() -> None:
    assert _event_from_workout({"title": "Bad Date", "date": "not-a-date"}) is None


def test_calendar_event_property_uses_next_scheduled_workout() -> None:
    """The entity's `event` (current/next) mirrors nextScheduledWorkout."""
    coord = MagicMock()
    coord.data = mock_activity_data()
    calendar = GarminScheduledWorkoutsCalendar(coord, "entry_id")

    event = calendar.event
    assert event is not None
    assert event.summary == "Benchmark Run"


async def test_calendar_get_events_filters_by_range() -> None:
    """async_get_events only returns workouts within [start, end)."""
    coord = MagicMock()
    coord.data = {
        "scheduledWorkouts": [
            {"date": "2026-09-12", "title": "In Range"},
            {"date": "2026-10-01", "title": "Out Of Range"},
        ]
    }
    calendar = GarminScheduledWorkoutsCalendar(coord, "entry_id")

    start = datetime(2026, 9, 1, tzinfo=UTC)
    end = datetime(2026, 9, 30, tzinfo=UTC)
    events = await calendar.async_get_events(None, start, end)

    assert len(events) == 1
    assert events[0].summary == "In Range"


async def test_calendar_get_events_empty_when_no_data() -> None:
    coord = MagicMock()
    coord.data = {}
    calendar = GarminScheduledWorkoutsCalendar(coord, "entry_id")

    start = datetime(2026, 9, 1, tzinfo=UTC)
    end = datetime(2026, 9, 30, tzinfo=UTC)
    assert await calendar.async_get_events(None, start, end) == []

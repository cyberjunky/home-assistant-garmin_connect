"""Calendar platform for Garmin Connect."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ActivityCoordinator, GarminConnectConfigEntry


def _event_from_workout(workout: dict[str, Any]) -> CalendarEvent | None:
    """Build a CalendarEvent from one scheduledWorkouts entry.

    Garmin only gives a date, not a time of day, so these are all-day
    events -- end is the day after start, matching the iCal/HA convention
    that an all-day event's end date is exclusive.
    """
    workout_date = workout.get("date")
    if not workout_date:
        return None
    try:
        start = date.fromisoformat(workout_date)
    except ValueError:
        return None
    return CalendarEvent(
        start=start,
        end=start + timedelta(days=1),
        summary=workout.get("title") or "Scheduled workout",
        description=workout.get("sportTypeKey"),
        uid=str(workout["id"]) if workout.get("id") is not None else None,
    )


def _event_from_goal(goal: dict[str, Any]) -> CalendarEvent | None:
    """Build a CalendarEvent from the training plan's goal event (target race).

    Same all-day-event shape as _event_from_workout -- Garmin gives a
    date, not a time.
    """
    goal_date = goal.get("date")
    event_name = goal.get("eventName")
    if not goal_date or not event_name:
        return None
    try:
        start = date.fromisoformat(goal_date)
    except ValueError:
        return None
    distance = goal.get("targetDistance")
    unit = goal.get("targetDistanceUnit")
    description = f"{distance} {unit}" if distance is not None and unit else goal.get("eventType")
    return CalendarEvent(
        start=start,
        end=start + timedelta(days=1),
        summary=event_name,
        description=description,
        uid=f"goal_{event_name}_{goal_date}",
    )


def _calendar_events(data: dict[str, Any]) -> list[CalendarEvent]:
    """Build events for upcomingEvents (races, plan goal events) and the goal event.

    The goal event is normally one of the upcoming events; deduplicated by uid.
    """
    events: dict[str | None, CalendarEvent] = {}
    for item in [*(data.get("upcomingEvents") or []), data.get("trainingPlanGoalEvent") or {}]:
        event = _event_from_goal(item)
        if event is not None:
            events.setdefault(event.uid, event)
    return list(events.values())


def _in_range(event: CalendarEvent, start_date: datetime, end_date: datetime, tzinfo: Any) -> bool:
    """Per HA's calendar contract: start_date bounds the event's own end and
    end_date bounds the event's own start (both exclusive) -- not a plain
    date-vs-date comparison, which would be wrong for an event spanning
    more than one day.
    """
    event_start = datetime.combine(event.start, time.min, tzinfo=tzinfo)
    event_end = datetime.combine(event.end, time.min, tzinfo=tzinfo)
    return event_end > start_date and event_start < end_date


class GarminScheduledWorkoutsCalendar(CoordinatorEntity[ActivityCoordinator], CalendarEntity):
    """Calendar of upcoming Garmin training-calendar sessions and events.

    Backed by ActivityCoordinator's scheduledWorkouts (current and next
    calendar month), upcomingEvents (races and plan goal events up to a
    year ahead) and trainingPlanGoalEvent, all from today onward
    (ha-garmin fetch_activity_data) -- browsing into the past in the
    Calendar UI shows nothing.

    For adaptive/Coach plans, don't expect a full plan's worth of
    sessions here: Garmin only assigns the *next* workout once it sees
    how the current one goes, so there's usually exactly one scheduled
    workout at a time plus the plan's goal event (the target race) far
    out on the calendar, with nothing in between -- confirmed by
    checking Garmin Connect's own calendar UI directly, not just this
    client's access to it. That gap is real on Garmin's side, not
    something being filtered out here.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "scheduled_workouts"

    def __init__(self, coordinator: ActivityCoordinator, entry_id: str) -> None:
        """Initialize the calendar."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_scheduled_workouts_calendar"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Garmin Connect",
            manufacturer="Garmin",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def available(self) -> bool:
        """Unavailable until the first activity fetch completes."""
        return super().available and self.coordinator.data is not None

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event -- scheduled workout or calendar event, whichever is sooner."""
        data = self.coordinator.data or {}
        candidates = [
            _event_from_workout(data.get("nextScheduledWorkout") or {}),
            *_calendar_events(data),
        ]
        upcoming = [event for event in candidates if event is not None]
        return min(upcoming, key=lambda event: event.start) if upcoming else None

    async def async_get_events(
        self, _hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return scheduled workouts and calendar events within the given range."""
        data = self.coordinator.data or {}
        workouts = data.get("scheduledWorkouts") or []
        tzinfo = start_date.tzinfo

        events = []
        for workout in workouts:
            event = _event_from_workout(workout)
            if event is not None and _in_range(event, start_date, end_date, tzinfo):
                events.append(event)

        events.extend(
            event
            for event in _calendar_events(data)
            if _in_range(event, start_date, end_date, tzinfo)
        )

        return events


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: GarminConnectConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Garmin Connect calendar."""
    coordinators = entry.runtime_data
    async_add_entities([GarminScheduledWorkoutsCalendar(coordinators.activity, entry.entry_id)])

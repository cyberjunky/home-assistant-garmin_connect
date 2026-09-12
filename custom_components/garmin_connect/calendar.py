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


class GarminScheduledWorkoutsCalendar(CoordinatorEntity[ActivityCoordinator], CalendarEntity):
    """Calendar of upcoming Garmin training-calendar sessions.

    Backed by ActivityCoordinator's scheduledWorkouts, which only covers
    the current and next calendar month and only dates from today onward
    (ha-garmin fetch_activity_data) -- browsing further out or into the
    past in the Calendar UI shows nothing.

    This is Garmin's calendar-service endpoint, not whatever the Garmin
    Connect app itself uses -- for adaptive/Coach plans the app can show
    upcoming days this endpoint doesn't return at all (that data lives
    behind a different, session-cookie-authenticated API this client
    can't reach). Expect fewer events here than in the app, sometimes
    none, even within the current/next month window.
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
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming scheduled workout."""
        data = self.coordinator.data or {}
        return _event_from_workout(data.get("nextScheduledWorkout") or {})

    async def async_get_events(
        self, _hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return scheduled workouts within the given range.

        Per HA's calendar contract, start_date bounds the event's own end
        and end_date bounds the event's own start (both exclusive) -- not
        a plain date-vs-date comparison, which would be wrong for an event
        spanning more than one day.
        """
        data = self.coordinator.data or {}
        workouts = data.get("scheduledWorkouts") or []
        tzinfo = start_date.tzinfo

        events = []
        for workout in workouts:
            event = _event_from_workout(workout)
            if event is None:
                continue
            event_start = datetime.combine(event.start, time.min, tzinfo=tzinfo)
            event_end = datetime.combine(event.end, time.min, tzinfo=tzinfo)
            if event_end > start_date and event_start < end_date:
                events.append(event)
        return events


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: GarminConnectConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Garmin Connect calendar."""
    coordinators = entry.runtime_data
    async_add_entities([GarminScheduledWorkoutsCalendar(coordinators.activity, entry.entry_id)])

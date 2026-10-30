"""Readable summaries of Garmin workout steps (from ha-garmin's workoutSteps)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

_STEP_NAMES = {
    "warmup": "Warm-up",
    "cooldown": "Cool-down",
    "interval": "Interval",
    "recovery": "Recovery",
    "rest": "Rest",
    "other": "Other",
}


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _clock(seconds: float) -> str:
    """Format seconds as m:ss or h:mm:ss."""
    total = round(seconds)
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def _distance(meters: float) -> str:
    return f"{meters / 1000:.2f} km" if meters >= 1000 else f"{meters:.0f} m"


def _range(low: float | None, high: float | None, fmt: Callable[[float], str]) -> str | None:
    # 0 is a real bound (0–100 W); only a range without any non-zero bound is empty.
    values = sorted(v for v in (low, high) if v is not None)
    if not any(values):
        return None
    if len(values) == 1 or values[0] == values[1]:
        return fmt(values[0])
    return f"{fmt(values[0])}–{fmt(values[1])}"


def _target(target_type: Any, low: Any, high: Any, zone: Any) -> str | None:
    """Describe a step target, e.g. "141–159 bpm" or "HR zone 2"."""
    if not isinstance(target_type, str) or target_type == "no.target":
        return None
    low, high = _number(low), _number(high)
    kind = target_type.split(".")[0]
    if isinstance(zone, int) and not isinstance(zone, bool) and not (low or high):
        names = {"heart": "HR", "power": "power", "pace": "pace", "speed": "speed"}
        return f"{names.get(kind, kind)} zone {zone}"
    if kind == "heart":
        text = _range(low, high, lambda v: f"{v:.0f}")
        return f"{text} bpm" if text else None
    if kind == "power":
        text = _range(low, high, lambda v: f"{v:.0f}")
        return f"{text} W" if text else None
    if kind == "pace":
        # Stored as speed (m/s); shown as time per km, fastest first.
        paces = [1000 / v for v in (low, high) if v] + [None, None]
        text = _range(paces[0], paces[1], _clock)
        return f"{text} /km" if text else None
    if kind == "speed":
        text = _range(low, high, lambda v: f"{v * 3.6:.1f}")
        return f"{text} km/h" if text else None
    if kind == "cadence":
        text = _range(low, high, lambda v: f"{v:.0f}")
        return f"cadence {text}" if text else None
    return None


def _end(condition: Any, value: Any) -> str | None:
    """Describe how a step ends, e.g. "1.00 km", "10:00" or "until lap press"."""
    value = _number(value)
    if condition == "lap.button":
        return "until lap press"
    if value is None:
        return None
    if condition == "distance":
        return _distance(value)
    if condition == "time":
        return _clock(value)
    if condition == "calories":
        return f"{value:.0f} kcal"
    return None


def step_summary(step: dict[str, Any]) -> str:
    """One line for a step; a repeat group lists its steps in parentheses."""
    if step.get("stepType") == "repeat":
        inner = "; ".join(step_summary(s) for s in step.get("steps") or [] if isinstance(s, dict))
        iterations = step.get("numberOfIterations")
        prefix = f"{iterations}× " if isinstance(iterations, int) else ""
        return f"{prefix}({inner})"
    step_type = str(step.get("stepType") or "step")
    name = _STEP_NAMES.get(step_type, step_type.replace("_", " ").title())
    parts = [name]
    if end := _end(step.get("endCondition"), step.get("endConditionValue")):
        parts.append(end)
    targets = [
        t
        for t in (
            _target(
                step.get("targetType"),
                step.get("targetValueOne"),
                step.get("targetValueTwo"),
                step.get("zoneNumber"),
            ),
            _target(
                step.get("secondaryTargetType"),
                step.get("secondaryTargetValueOne"),
                step.get("secondaryTargetValueTwo"),
                step.get("secondaryZoneNumber"),
            ),
        )
        if t
    ]
    text = " ".join(parts)
    if targets:
        text += " @ " + ", ".join(targets)
    if sport := step.get("sportType"):
        text = f"{str(sport).replace('_', ' ').title()}: {text}"
    return text


def steps_summary(workout: dict[str, Any]) -> list[str]:
    """Readable lines for a workout's workoutSteps (empty when it has none)."""
    return [step_summary(s) for s in workout.get("workoutSteps") or [] if isinstance(s, dict)]

"""Tests for the readable workout step summaries."""

import pytest

from custom_components.garmin_connect.workout import step_summary, steps_summary


@pytest.mark.parametrize(
    ("step", "expected"),
    [
        (
            {"stepType": "warmup", "endCondition": "lap.button", "targetType": "no.target"},
            "Warm-up until lap press",
        ),
        (
            {
                "stepType": "interval",
                "endCondition": "distance",
                "endConditionValue": 4828.02,
                "targetType": "heart.rate.zone",
                "targetValueOne": 141.0,
                "targetValueTwo": 159.0,
            },
            "Interval 4.83 km @ 141–159 bpm",
        ),
        (
            {
                "stepType": "interval",
                "endCondition": "distance",
                "endConditionValue": 400.0,
                "targetType": "pace.zone",
                # m/s; the faster pace is shown first.
                "targetValueOne": 3.7037,
                "targetValueTwo": 4.1667,
            },
            "Interval 400 m @ 4:00–4:30 /km",
        ),
        (
            {
                "stepType": "recovery",
                "endCondition": "time",
                "endConditionValue": 90.0,
                "targetType": "heart.rate.zone",
                "zoneNumber": 2,
            },
            "Recovery 1:30 @ HR zone 2",
        ),
        (
            {
                "stepType": "cooldown",
                "endCondition": "time",
                "endConditionValue": 3900.0,
                "targetType": "power.zone",
                "targetValueOne": 180,
                "targetValueTwo": 220,
                "secondaryTargetType": "cadence",
                "secondaryTargetValueOne": 85,
                "secondaryTargetValueTwo": 95,
            },
            "Cool-down 1:05:00 @ 180–220 W, cadence 85–95",
        ),
        (
            {
                "stepType": "interval",
                "endCondition": "time",
                "endConditionValue": 600.0,
                "sportType": "cycling",
            },
            "Cycling: Interval 10:00",
        ),
        (
            {
                "stepType": "interval",
                "endCondition": "time",
                "endConditionValue": 300.0,
                "targetType": "power.zone",
                "targetValueOne": 0,
                "targetValueTwo": 100,
            },
            "Interval 5:00 @ 0–100 W",
        ),
        (
            {
                "stepType": "interval",
                "endCondition": "time",
                "endConditionValue": 300.0,
                "targetType": "power.zone",
                "targetValueOne": 0,
                "targetValueTwo": 0,
            },
            "Interval 5:00",
        ),
        ({"stepType": "main_set"}, "Main Set"),
    ],
)
def test_step_summary(step: dict, expected: str):
    """A step reads as its name, how it ends and its targets."""
    assert step_summary(step) == expected


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        (
            {"targetType": "heart.rate.zone", "targetValueOne": 150.0},
            "Interval 5:00 @ 150 bpm",
        ),
        (
            {"targetType": "heart.rate.zone", "targetValueOne": 150.0, "targetValueTwo": 150.0},
            "Interval 5:00 @ 150 bpm",
        ),
        (
            {"targetType": "pace.zone", "targetValueTwo": 4.0},
            "Interval 5:00 @ 4:10 /km",
        ),
        (
            {"targetType": "speed.zone", "targetValueOne": 5.0, "targetValueTwo": 2.5},
            "Interval 5:00 @ 9.0–18.0 km/h",
        ),
        (
            {"targetType": "speed.zone", "targetValueOne": 0, "targetValueTwo": 0},
            "Interval 5:00",
        ),
        (
            {"targetType": "resistance.zone", "targetValueOne": 3, "targetValueTwo": 5},
            "Interval 5:00",
        ),
    ],
    ids=["single-bound", "equal-bounds", "single-pace", "speed", "empty-speed", "unknown-kind"],
)
def test_step_target(target: dict, expected: str):
    """A one-value range shows one number, speed shows km/h, unknown targets are left out."""
    step = {"stepType": "interval", "endCondition": "time", "endConditionValue": 300.0}
    assert step_summary(step | target) == expected


@pytest.mark.parametrize(
    ("condition", "value", "expected"),
    [
        ("calories", 250.4, "Interval 250 kcal"),
        ("reps", 10, "Interval 10 reps"),
        ("heart.rate", 150, "Interval"),
        ("time", None, "Interval"),
        ("time", True, "Interval"),
    ],
    ids=["calories", "reps", "unknown-condition", "no-value", "bool-value"],
)
def test_step_end_condition(condition: str, value: object, expected: str):
    """Calories end a step in kcal; unknown conditions and non-numeric values are left out."""
    step = {"stepType": "interval", "endCondition": condition, "endConditionValue": value}
    assert step_summary(step) == expected


def test_repeat_group_lists_its_steps():
    """A repeat group shows its iteration count and its steps in parentheses."""
    step = {
        "stepType": "repeat",
        "numberOfIterations": 4,
        "steps": [
            {"stepType": "interval", "endCondition": "distance", "endConditionValue": 400.0},
            {"stepType": "recovery", "endCondition": "time", "endConditionValue": 90.0},
        ],
    }
    assert step_summary(step) == "4× (Interval 400 m; Recovery 1:30)"


def test_workout_without_steps_has_no_summary():
    """A workout without workoutSteps has no summary lines."""
    assert steps_summary({"title": "Benchmark Run"}) == []

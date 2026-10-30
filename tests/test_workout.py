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
    assert step_summary(step) == expected


def test_repeat_group_lists_its_steps():
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
    assert steps_summary({"title": "Benchmark Run"}) == []

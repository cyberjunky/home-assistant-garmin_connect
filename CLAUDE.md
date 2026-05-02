# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Communication style

This user prefers caveman mode: terse, no filler, fragments OK, short synonyms. Drop articles/hedging/pleasantries. Technical terms exact. Code unchanged. Pattern: `[thing] [action] [reason]. [next step].`

## Commands

```bash
scripts/setup       # Install dependencies and pre-commit hooks
scripts/test        # Run pytest with coverage (pass extra args after --)
scripts/lint        # Run pre-commit + vulture dead-code check
scripts/develop     # Start local Home Assistant instance with the integration loaded
```

Run a single test file:
```bash
pytest tests/test_sensor.py -v
```

## Architecture

This is a Home Assistant custom integration that polls the Garmin Connect cloud API via the [`ha-garmin`](https://github.com/cyberjunky/ha-garmin) library. The library is the only Garmin API dependency — all data fetching happens there.

### Data flow

Each data domain has its own `DataUpdateCoordinator` subclass in [coordinator.py](custom_components/garmin_connect/coordinator.py). All coordinators share the same `GarminClient` and `GarminAuth` instances, and each calls one `client.fetch_*_data()` method per poll:

| Coordinator | Data |
|---|---|
| `CoreCoordinator` | Daily summary, steps, sleep, HR, stress, SpO2, body battery (~50 sensors) |
| `ActivityCoordinator` | Last activity, last 10 activities, polyline, workouts (~5 sensors) |
| `TrainingCoordinator` | Readiness, VO2max, HRV, training status, scores (~11 sensors) |
| `BodyCoordinator` | Weight, BMI, hydration, fitness age, body composition (~17 sensors) |
| `GoalsCoordinator` | Badges, points, active goals (~6 sensors) |
| `GearCoordinator` | Gear stats (dynamic sensors per item), alarms |
| `BloodPressureCoordinator` | Latest BP reading (~3 sensors) |
| `MenstrualCoordinator` | Menstrual data (~9 sensors, disabled by default) |

### Sensor definitions

All sensors are declared as `GarminConnectSensorEntityDescription` tuples in [sensor.py](custom_components/garmin_connect/sensor.py), grouped by coordinator. Each description has:
- `coordinator_type` — which coordinator feeds it
- `value_fn` — lambda to extract the state value from coordinator data (falls back to `key` lookup if omitted)
- `attributes_fn` — lambda to extract extra state attributes
- `preserve_value=True` — retains last non-`None` value (used for weight, sleep, HRV which go `None` mid-day)

### Key data facts from `ha-garmin`

- `startTimeLocal` is **dropped** by the library; use `startTime` (UTC datetime) instead. In templates: `(a.startTime | as_datetime | as_local).strftime('%Y-%m-%d')`
- `activityType` is simplified to a plain string (`"running"`, `"cycling"`, etc.)
- `polyline` (GPS coordinates as `[{lat, lon}]`) lives on `lastActivityRoute` sensor, **not** `lastActivity`

### Custom Lovelace card

`www/garmin-polyline-card.js` renders activity routes using Leaflet. Users must copy **all three files** from `www/` to `<config>/www/`: the card JS plus `leaflet.js` and `leaflet.css`.

### Entity unique IDs

Format: `{entry_id}_{sensor_key}`. The v1→v2 migration in [\_\_init\_\_.py](custom_components/garmin_connect/__init__.py) rewrites unique IDs from the old `{email}_{key}` format and triggers reauth (tokens are incompatible between versions).

"""Tests that every translation file matches the English source."""

import json
import re
from pathlib import Path

import pytest

COMPONENT = Path(__file__).parent.parent / "custom_components" / "garmin_connect"
LANGUAGES = sorted(p.stem for p in (COMPONENT / "translations").glob("*.json") if p.stem != "en")


def _flatten(data: dict, prefix: str = "") -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in data.items():
        if isinstance(value, dict):
            out.update(_flatten(value, f"{prefix}{key}."))
        else:
            out[f"{prefix}{key}"] = value
    return out


def _load(name: str) -> dict[str, str]:
    path = COMPONENT / name if name == "strings.json" else COMPONENT / "translations" / name
    return _flatten(json.loads(path.read_text(encoding="utf-8")))


def test_english_matches_strings() -> None:
    """translations/en.json is generated from strings.json and must match it."""
    assert _load("en.json") == _load("strings.json")


@pytest.mark.parametrize("language", LANGUAGES)
def test_translation_has_every_key(language: str) -> None:
    """A language lists exactly the English keys, so nothing falls back silently."""
    english = _load("en.json")
    translated = _load(f"{language}.json")
    assert sorted(english.keys() - translated.keys()) == []
    assert sorted(translated.keys() - english.keys()) == []


@pytest.mark.parametrize("language", LANGUAGES)
def test_translation_keeps_placeholders(language: str) -> None:
    """Placeholders like {error} must survive translation or the message breaks."""
    english = _load("en.json")
    translated = _load(f"{language}.json")
    placeholder = re.compile(r"\{(\w+)\}")
    broken = [
        key
        for key, text in english.items()
        if set(placeholder.findall(text)) != set(placeholder.findall(translated.get(key, "")))
    ]
    assert broken == []

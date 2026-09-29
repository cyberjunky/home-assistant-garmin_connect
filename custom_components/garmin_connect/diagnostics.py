"""Diagnostics support for Garmin Connect."""

from __future__ import annotations

from dataclasses import fields
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import GarminConnectConfigEntry

TO_REDACT = {
    "token",
    "refresh_token",
    "client_id",
    "displayName",
    "fullName",
    "userName",
    "email",
    "profileImageUrlMedium",
    "profileImageUrlSmall",
    "profileImageUrlLarge",
    # A full GPS track is both huge and a location trace.
    "polyline",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: GarminConnectConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinators = entry.runtime_data

    coordinator_info: dict[str, Any] = {}
    for field in fields(coordinators):
        coordinator = getattr(coordinators, field.name)
        data = coordinator.data or {}
        coordinator_info[field.name] = {
            "last_update_success": coordinator.last_update_success,
            "update_interval_seconds": (
                coordinator.update_interval.total_seconds() if coordinator.update_interval else None
            ),
            "data_keys_count": len(data),
            "data": async_redact_data(data, TO_REDACT),
        }

    return {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "coordinators": coordinator_info,
    }

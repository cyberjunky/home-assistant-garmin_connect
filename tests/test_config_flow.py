"""Tests for Garmin Connect config flow."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.garmin_connect.const import DOMAIN


async def test_form_user(hass: HomeAssistant, _mock_garmin_client) -> None:
    """Test user config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test invalid authentication."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "custom_components.garmin_connect.config_flow.Garmin"
    ) as mock_garmin:
        from garminconnect import GarminConnectAuthenticationError
        mock_garmin.return_value.login.side_effect = GarminConnectAuthenticationError("Invalid")

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "test@test.com", "password": "wrong"},
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}

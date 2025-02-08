"""Config flow for Garmin Connect integration."""

import logging

from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)
from homeassistant import config_entries
from homeassistant.const import CONF_ID, CONF_PASSWORD, CONF_USERNAME
import voluptuous as vol

from .const import DOMAIN, CONF_MFA

_LOGGER = logging.getLogger(__name__)


class GarminConnectConfigFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Garmin Connect."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self.mfa_data_schema = {
            vol.Required(CONF_MFA): str,
        }
        self._mfa_code: str | None = None

    async def _show_setup_form(self, errors=None):
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_USERNAME): str,
                 vol.Required(CONF_PASSWORD): str}
            ),
            errors=errors or {},
        )

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is None:
            return await self._show_setup_form()

        username = user_input[CONF_USERNAME]
        password = user_input[CONF_PASSWORD]

        api = Garmin(username, password, prompt_mfa=self.get_mfa)

        errors = {}
        try:
            await self.hass.async_add_executor_job(api.login)
        except GarminConnectConnectionError:
            errors["base"] = "cannot_connect"
            return await self._show_setup_form(errors)
        except GarminConnectAuthenticationError:
            errors["base"] = "invalid_auth"
            return await self._show_setup_form(errors)
        except GarminConnectTooManyRequestsError:
            errors["base"] = "too_many_requests"
            return await self._show_setup_form(errors)
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
            return await self._show_setup_form(errors)

        await self.async_set_unique_id(username)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=username,
            data={
                CONF_ID: username,
                CONF_USERNAME: username,
                CONF_PASSWORD: password,
            },
        )

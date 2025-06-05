"""Config flow for Garmin Connect integration."""

import logging
from collections.abc import Mapping
from typing import Any, cast
import requests
from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ID, CONF_TOKEN, CONF_PASSWORD, CONF_USERNAME
import voluptuous as vol
import garth

from .const import CONF_MFA, DOMAIN

_LOGGER = logging.getLogger(__name__)


class GarminConnectConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Garmin Connect."""

    VERSION = 1

    def __init__(self) -> None:
        """
        Initializes the Garmin Connect configuration flow handler.
        
        Sets up schemas for user credentials and MFA input, and initializes internal state variables for API client, login results, MFA code, credentials, and region flag.
        """
        self.data_schema = {
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
        }
        self.mfa_data_schema = {
            vol.Required(CONF_MFA): str,
        }

        self._api = None
        self._login_result1: Any = None
        self._login_result2: Any = None
        self._mfa_code: str | None = None
        self._username: str | None = None
        self._password: str | None = None
        self._in_china = False

    async def _async_garmin_connect_login(self, step_id: str) -> ConfigFlowResult:
        """
        Attempts to authenticate the user with Garmin Connect and handles login errors or MFA requirements.
        
        If the user is located in China, configures the API client accordingly. Initiates the login process and, if multi-factor authentication is required, transitions to the MFA step. Handles specific authentication and connection errors, returning appropriate error messages to the user. On successful authentication, proceeds to create the configuration entry.
        """
        errors = {}

        # Check if the user resides in China
        country = self.hass.config.country
        if country == "CN":
            self._in_china = True

        self._api = Garmin(email=self._username,
                           password=self._password, return_on_mfa=True, is_cn=self._in_china)

        try:
            self._login_result1, self._login_result2 = await self.hass.async_add_executor_job(self._api.login)

            if self._login_result1 == "needs_mfa":  # MFA is required
                return await self.async_step_mfa()

        except GarminConnectConnectionError:
            errors = {"base": "cannot_connect"}
        except GarminConnectAuthenticationError:
            errors = {"base": "invalid_auth"}
        except GarminConnectTooManyRequestsError:
            errors = {"base": "too_many_requests"}
        except requests.exceptions.HTTPError as err:
            if err.response.status_code == 403:
                errors = {"base": "invalid_auth"}
            elif err.response.status_code == 429:
                errors = {"base": "too_many_requests"}
            else:
                errors = {"base": "cannot_connect"}
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors = {"base": "unknown"}

        if errors:
            return self.async_show_form(
                step_id=step_id, data_schema=vol.Schema(self.data_schema), errors=errors
            )

        return await self._async_create_entry()

    async def _async_garmin_connect_mfa_login(self) -> ConfigFlowResult:
        """
        Completes the Garmin Connect login process using the provided MFA code.
        
        Attempts to resume the login session with the stored MFA code. If the MFA code is invalid or an error occurs, prompts the user to re-enter the code. On success, creates the configuration entry.
        """
        try:
            await self.hass.async_add_executor_job(self._api.resume_login, self._login_result2, self._mfa_code)

        except garth.exc.GarthException as err:
            _LOGGER.error("Error during MFA login: %s", err)
            return self.async_show_form(
                step_id="mfa",
                data_schema=vol.Schema(self.mfa_data_schema),
                errors={"base": "invalid_mfa_code"},
            )

        return await self._async_create_entry()

    async def _async_create_entry(self) -> ConfigFlowResult:
        """
        Creates or updates the configuration entry for the Garmin Connect integration.
        
        If an entry with the same username exists, updates its data and reloads it; otherwise, creates a new entry with the username as the unique ID and stores the serialized API token.
        """
        config_data = {
            CONF_ID: self._username,
            CONF_USERNAME: self._username,
            CONF_TOKEN: self._api.garth.dumps(),
        }
        existing_entry = await self.async_set_unique_id(self._username)

        if existing_entry:
            return self.async_update_reload_and_abort(existing_entry, data=config_data)

        return self.async_create_entry(
            title=cast(str, self._username), data=config_data
        )

    async def async_step_user(
            self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """
            Handles the initial step of the configuration flow triggered by the user.
            
            If no input is provided, displays a form requesting username and password. Otherwise, stores the provided credentials and attempts to authenticate with Garmin Connect.
            """
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=vol.Schema(self.data_schema)
            )

        self._username = user_input[CONF_USERNAME]
        self._password = user_input[CONF_PASSWORD]

        return await self._async_garmin_connect_login(step_id="user")

    async def async_step_mfa(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """
        Handles the multi-factor authentication (MFA) step during the configuration flow.
        
        If no user input is provided, displays a form requesting the MFA code. If input is received, stores the MFA code for further authentication processing.
        """
        if user_input is None:
            return self.async_show_form(
                step_id="mfa", data_schema=vol.Schema(self.mfa_data_schema)
            )

        self._mfa_code = user_input[CONF_MFA]
-        _LOGGER.info(f"MFA CODE: {self._mfa_code}")
+        _LOGGER.debug("MFA code received")

        return await self._async_garmin_connect_mfa_login()

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """
        Initiates the reauthorization flow using existing entry data.
        
        Extracts the username from the provided entry data and proceeds to the reauthorization confirmation step.
        """
        self._username = entry_data[CONF_USERNAME]

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """
        Handles the confirmation step for reauthorizing the Garmin Connect integration.
        
        Prompts the user to re-enter their username and password. Upon receiving input, attempts to log in with the provided credentials to complete the reauthorization process.
        """
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_USERNAME, default=self._username): str,
                        vol.Required(CONF_PASSWORD): str,
                    }
                ),
            )

        self._username = user_input[CONF_USERNAME]
        self._password = user_input[CONF_PASSWORD]

        return await self._async_garmin_connect_login(step_id="reauth_confirm")

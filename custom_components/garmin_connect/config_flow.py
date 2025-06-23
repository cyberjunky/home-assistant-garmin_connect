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
        Initialize schemas and internal state for the Garmin Connect configuration flow handler.
        
        Sets up validation schemas for user credentials and MFA input, and initializes variables for API client, login results, MFA code, credentials, and region detection.
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
        Authenticate the user with Garmin Connect and handle login errors or multi-factor authentication requirements.
        
        If the user is located in China, configures the API client for the region. Initiates the login process and, if multi-factor authentication is needed, transitions to the MFA step. Handles specific authentication and connection errors, returning appropriate error messages to the user. On successful authentication, proceeds to create or update the configuration entry.
        
        Parameters:
            step_id (str): The current step identifier in the configuration flow.
        
        Returns:
            ConfigFlowResult: The result of the configuration flow step, which may be a form with errors, a transition to MFA, or entry creation.
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
        Complete the Garmin Connect authentication process using the stored multi-factor authentication (MFA) code.
        
        If the MFA code is invalid or an error occurs, prompts the user to re-enter the code. On successful authentication, creates or updates the configuration entry.
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
        Create or update the configuration entry for the Garmin Connect integration using the current user's credentials and API token.
        
        If an entry with the same username exists, its data is updated and the entry is reloaded; otherwise, a new entry is created with the username as the unique ID and the serialized API token.
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
            Handle the initial user step of the configuration flow.
            
            If no input is provided, displays a form to collect username and password. If credentials are submitted, stores them and attempts authentication with Garmin Connect.
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
        Handle the multi-factor authentication (MFA) step in the configuration flow.
        
        If user input is not provided, displays a form to collect the MFA code. If input is provided, stores the MFA code and proceeds with MFA authentication.
        """
        if user_input is None:
            return self.async_show_form(
                step_id="mfa", data_schema=vol.Schema(self.mfa_data_schema)
            )

        self._mfa_code = user_input[CONF_MFA]
        _LOGGER.debug("MFA code received")

        return await self._async_garmin_connect_mfa_login()

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """
        Start the reauthorization process using existing configuration entry data.
        
        Extracts the username from the entry data and advances to the reauthorization confirmation step.
        """
        self._username = entry_data[CONF_USERNAME]

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """
        Prompt the user to re-enter their username and password to confirm reauthorization of the Garmin Connect integration.
        
        If credentials are provided, attempts to log in and complete the reauthorization process.
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

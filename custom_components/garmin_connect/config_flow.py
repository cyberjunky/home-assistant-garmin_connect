"""Config flow for Garmin Connect integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from aiohttp import ClientError
from ha_garmin import (
    GarminAuth,
    GarminAuthError,
    GarminClient,
    GarminConnectError,
    GarminMFARequired,
    GarminRateLimitError,
)
from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import (
    CONF_CLIENT_ID,
    CONF_REFRESH_TOKEN,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

STEP_MFA_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("mfa_code"): str,
    }
)


class GarminConnectConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Garmin Connect."""

    VERSION = 2

    def __init__(self) -> None:
        """Initialize config flow."""
        self._auth: GarminAuth | None = None
        self._username: str | None = None
        self._is_cn: bool = False

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return GarminConnectOptionsFlow()

    def _token_data(self) -> dict[str, Any]:
        """Return token data from current auth state."""
        if TYPE_CHECKING:
            assert self._auth is not None
        return {
            CONF_TOKEN: self._auth.di_token,
            CONF_REFRESH_TOKEN: self._auth.di_refresh_token,
            CONF_CLIENT_ID: self._auth.di_client_id,
        }

    async def _async_login(self, username: str, password: str) -> None:
        """Run Garmin login in the executor."""
        if TYPE_CHECKING:
            assert self._auth is not None
        await self.hass.async_add_executor_job(
            self._auth.login,
            username,
            password,
        )

    async def _async_complete_mfa(self, mfa_code: str) -> None:
        """Run Garmin MFA completion in the executor."""
        if TYPE_CHECKING:
            assert self._auth is not None
        await self.hass.async_add_executor_job(
            self._auth.complete_mfa,
            mfa_code,
        )

    async def _async_finish_reauth(self) -> ConfigFlowResult:
        """Update tokens on the existing entry and reload it."""
        entry = self._get_reauth_entry()
        self.hass.config_entries.async_update_entry(
            entry, data=self._token_data())
        await self.hass.config_entries.async_reload(entry.entry_id)
        return self.async_abort(reason="reauth_successful")

    async def _async_finish_reconfigure(self) -> ConfigFlowResult:
        """Update tokens on the existing entry and reload it."""
        entry = self._get_reconfigure_entry()
        self.hass.config_entries.async_update_entry(
            entry, data=self._token_data())
        await self.hass.config_entries.async_reload(entry.entry_id)
        return self.async_abort(reason="reconfigure_successful")

    async def _async_create_new_entry(self, username: str) -> ConfigFlowResult:
        """Finalize a new config entry after successful authentication."""
        if TYPE_CHECKING:
            assert self._auth is not None
        unique_id = username
        try:
            client = GarminClient(self._auth, is_cn=self._is_cn)
            profile = await client.get_user_profile()
        except (GarminConnectError, ClientError):
            pass
        else:
            unique_id = str(profile.profile_id)
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=username,
            data=self._token_data(),
        )

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._username = user_input[CONF_USERNAME]
            self._is_cn = self.hass.config.country == "CN"
            self._auth = GarminAuth(is_cn=self._is_cn)

            try:
                await self._async_login(
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )
            except GarminMFARequired:
                return await self.async_step_mfa()
            except GarminRateLimitError:
                errors["base"] = "rate_limit"
            except GarminAuthError:
                errors["base"] = "invalid_auth"
            except GarminConnectError:
                errors["base"] = "unknown"
            else:
                return await self._async_create_new_entry(user_input[CONF_USERNAME])

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_mfa(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle MFA step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if TYPE_CHECKING:
                assert self._auth is not None

            try:
                await self._async_complete_mfa(user_input["mfa_code"])
            except GarminRateLimitError:
                errors["base"] = "rate_limit"
            except GarminAuthError:
                errors["base"] = "invalid_mfa"
            except GarminConnectError:
                errors["base"] = "unknown"

            else:
                if self.source == SOURCE_REAUTH:
                    return await self._async_finish_reauth()
                if self.source == SOURCE_RECONFIGURE:
                    return await self._async_finish_reconfigure()
                if TYPE_CHECKING:
                    assert self._username is not None
                return await self._async_create_new_entry(self._username)

        return self.async_show_form(
            step_id="mfa",
            data_schema=STEP_MFA_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """Handle re-authentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-authentication confirmation."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._username = user_input[CONF_USERNAME]
            self._is_cn = self.hass.config.country == "CN"
            self._auth = GarminAuth(is_cn=self._is_cn)

            try:
                await self._async_login(
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )
            except GarminMFARequired:
                return await self.async_step_mfa()
            except GarminRateLimitError:
                errors["base"] = "rate_limit"
            except GarminAuthError:
                errors["base"] = "invalid_auth"
            except GarminConnectError:
                errors["base"] = "unknown"
            else:
                return await self._async_finish_reauth()

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._username = user_input[CONF_USERNAME]
            self._is_cn = self.hass.config.country == "CN"
            self._auth = GarminAuth(is_cn=self._is_cn)

            try:
                await self._async_login(
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )
            except GarminMFARequired:
                return await self.async_step_mfa()
            except GarminRateLimitError:
                errors["base"] = "rate_limit"
            except GarminAuthError:
                errors["base"] = "invalid_auth"
            except GarminConnectError:
                errors["base"] = "unknown"
            else:
                return await self._async_finish_reconfigure()

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )


class GarminConnectOptionsFlow(OptionsFlow):
    """Handle options flow for Garmin Connect."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_scan_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=current_scan_interval,
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=MIN_SCAN_INTERVAL,
                                  max=MAX_SCAN_INTERVAL),
                    ),
                }
            ),
        )

"""Config flow for SplitPro integration."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SplitProApiError, SplitProClient
from .const import (
    CONF_API_KEY,
    CONF_SCAN_INTERVAL,
    CONF_URL,
    CONF_USER_EMAIL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL, description={"suggested_value": "https://splitpro.example.com"}): str,
        vol.Required(CONF_API_KEY): str,
        vol.Required(CONF_USER_EMAIL): str,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
            int, vol.Range(min=1, max=60)
        ),
    }
)


async def _validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Try to connect and return user info. Raises on failure."""
    session = async_get_clientsession(hass)
    client = SplitProClient(
        session=session,
        base_url=data[CONF_URL],
        api_key=data[CONF_API_KEY],
        user_email=data[CONF_USER_EMAIL],
    )
    summary = await client.get_summary(limit=1)
    user = summary.get("user", {})
    return {"title": f"SplitPro – {user.get('name') or data[CONF_USER_EMAIL]}"}


class SplitProConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SplitPro."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await _validate_input(self.hass, user_input)
            except SplitProApiError as err:
                _LOGGER.error("SplitPro API validation error: %s", err)
                if "401" in str(err):
                    errors["base"] = "invalid_auth"
                elif "404" in str(err):
                    errors["base"] = "user_not_found"
                else:
                    errors["base"] = "cannot_connect"
            except aiohttp.ClientError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error during SplitPro setup")
                errors["base"] = "unknown"
            else:
                # Prevent duplicate entries for same URL + email
                await self.async_set_unique_id(
                    f"{user_input[CONF_URL]}:{user_input[CONF_USER_EMAIL]}"
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

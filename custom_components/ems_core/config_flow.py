"""Config Flow für die EMS-Core-Integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import EMSApiClient, EMSApiError, EMSAuthError
from .const import CONF_EMAIL, CONF_HOST, CONF_PASSWORD, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default="http://homeassistant.local:8090"): str,
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def _validate(hass: HomeAssistant, data: dict[str, Any]) -> None:
    session = async_get_clientsession(hass)
    client = EMSApiClient(session, data[CONF_HOST], data[CONF_EMAIL], data[CONF_PASSWORD])
    if not await client.health():
        raise EMSApiError("EMS-Core nicht erreichbar")
    await client.login()


class EMSCoreConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config Flow: Host + Login-Daten, gleicher Account wie im EMS-Dashboard."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_HOST])
            self._abort_if_unique_id_configured()

            try:
                await _validate(self.hass, user_input)
            except EMSAuthError:
                errors["base"] = "invalid_auth"
            except EMSApiError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001 - unerwartete Fehler nicht verschlucken, aber sauber melden
                _LOGGER.exception("Unerwarteter Fehler beim Verbinden mit EMS-Core")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=f"EMS Core ({user_input[CONF_HOST]})", data=user_input
                )

        return self.async_show_form(step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors)

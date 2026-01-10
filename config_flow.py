"""Config flow for Petlibro Local integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME

from .const import CONF_MODEL, CONF_SERIAL, DOMAIN


class PetlibroLocalConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Petlibro Local."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Use serial as unique ID to prevent duplicate entries
            await self.async_set_unique_id(user_input[CONF_SERIAL])
            self._abort_if_unique_id_configured()

            title = user_input.get(CONF_NAME) or f"Petlibro {user_input[CONF_MODEL]}"
            return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MODEL, default="PLAF103"): str,
                    vol.Required(CONF_SERIAL): str,
                    vol.Optional(CONF_NAME): str,
                }
            ),
            errors=errors,
        )

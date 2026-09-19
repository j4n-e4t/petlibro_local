"""Config flow for Petlibro Local integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_FEEDING_PLAN_REPLY,
    CONF_MODEL,
    CONF_SERIAL,
    DEFAULT_FEEDING_PLAN_REPLY,
    DOMAIN,
    FEEDING_PLAN_REPLY_OPTIONS,
)


class PetlibroLocalConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Petlibro Local."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return PetlibroLocalOptionsFlow(config_entry)

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


class PetlibroLocalOptionsFlow(OptionsFlow):
    """Handle options flow for Petlibro Local."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            # Update the config entry title if name changed
            new_name = user_input.get(CONF_NAME)
            if new_name:
                self.hass.config_entries.async_update_entry(
                    self._config_entry,
                    title=new_name,
                )
            return self.async_create_entry(title="", data=user_input)

        options = self._config_entry.options

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_NAME, default=self._config_entry.title
                    ): str,
                    vol.Optional(
                        CONF_FEEDING_PLAN_REPLY,
                        default=options.get(
                            CONF_FEEDING_PLAN_REPLY, DEFAULT_FEEDING_PLAN_REPLY
                        ),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=FEEDING_PLAN_REPLY_OPTIONS,
                            translation_key=CONF_FEEDING_PLAN_REPLY,
                            mode=SelectSelectorMode.LIST,
                        )
                    ),
                }
            ),
        )

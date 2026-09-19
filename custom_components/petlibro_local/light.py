"""Light platform for Petlibro Local integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CMD_ATTR_SET, CONF_SERIAL, DOMAIN
from .coordinator import PetlibroCoordinator
from .entity import PetlibroAttributeEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Petlibro Local lights from a config entry."""
    coordinator: PetlibroCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    async_add_entities([PetlibroIndicatorLight(entry, coordinator)])


class PetlibroIndicatorLight(PetlibroAttributeEntity, LightEntity):
    """Representation of the Petlibro indicator lights."""

    _attr_translation_key = "indicator_lights"
    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_entity_category = EntityCategory.CONFIG
    _state_key = "lightSwitch"

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: PetlibroCoordinator,
    ) -> None:
        """Initialize the indicator light."""
        super().__init__(entry, coordinator)
        self._attr_unique_id = f"{entry.data[CONF_SERIAL]}_indicator_lights"

    @property
    def is_on(self) -> bool | None:
        """Return true if light is on."""
        return self._is_on

    async def _send_command(self, state: bool) -> None:
        """Set the light, then wait for the device to confirm."""
        await self._coordinator.async_send_command(
            CMD_ATTR_SET,
            lightSwitch=state,
            lightAgingType=1,
            # Always true, matching every captured app command.
            filterLedSwitch=True,
        )

        self._is_on = state
        self.async_write_ha_state()
        _LOGGER.debug("Indicator lights set to %s and acked", state)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        await self._send_command(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self._send_command(False)

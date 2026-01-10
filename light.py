"""Light platform for Petlibro Local integration."""
from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CMD_ATTR_GET,
    CMD_ATTR_PUSH,
    CMD_ATTR_SET,
    CONF_SERIAL,
    DOMAIN,
)
from .coordinator import PetlibroCoordinator
from .entity import PetlibroBaseEntity
from .helpers import publish_command

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Petlibro Local lights from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    topics = data["topics"]
    coordinator: PetlibroCoordinator = data["coordinator"]

    entities = [
        PetlibroIndicatorLight(entry, topics, coordinator),
    ]
    async_add_entities(entities)


class PetlibroIndicatorLight(PetlibroBaseEntity, LightEntity):
    """Representation of the Petlibro indicator lights."""

    _attr_name = "Indicator Lights"
    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        entry: ConfigEntry,
        topics: dict[str, str],
        coordinator: PetlibroCoordinator,
    ) -> None:
        """Initialize the indicator light."""
        super().__init__(entry, topics)
        self._coordinator = coordinator
        self._is_on: bool | None = None
        self._attr_unique_id = f"{entry.data[CONF_SERIAL]}_indicator_lights"
        self._unsubscribe: Callable[[], None] | None = None

    @property
    def is_on(self) -> bool | None:
        """Return true if light is on."""
        return self._is_on

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._is_on is not None

    @callback
    def _handle_event(self, payload: dict[str, Any]) -> None:
        """Handle event messages from coordinator."""
        cmd = payload.get("cmd")

        if cmd in (CMD_ATTR_GET, CMD_ATTR_PUSH) and "lightSwitch" in payload:
            self._is_on = payload["lightSwitch"]
            self.async_write_ha_state()
            _LOGGER.debug(
                "Indicator lights state updated to %s (from %s)",
                self._is_on,
                cmd,
            )

    async def async_added_to_hass(self) -> None:
        """Register with coordinator when added to hass."""
        self._unsubscribe = self._coordinator.register_event_listener(
            self._handle_event
        )

    async def async_will_remove_from_hass(self) -> None:
        """Unregister from coordinator when removed."""
        if self._unsubscribe:
            self._unsubscribe()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        await publish_command(
            self.hass,
            self._command_topic,
            CMD_ATTR_SET,
            lightSwitch=True,
            lightAgingType=1,
            filterLedSwitch=True,
        )

        _LOGGER.debug("Sent turn on command for indicator lights")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await publish_command(
            self.hass,
            self._command_topic,
            CMD_ATTR_SET,
            lightSwitch=False,
            lightAgingType=1,
            filterLedSwitch=False,
        )

        _LOGGER.debug("Sent turn off command for indicator lights")

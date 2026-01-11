"""Event platform for Petlibro Local integration."""
from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from homeassistant.components.event import EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CMD_GRAIN_OUTPUT,
    CONF_SERIAL,
    DOMAIN,
)
from .coordinator import PetlibroCoordinator
from .entity import PetlibroBaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Petlibro Local events from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    topics = data["topics"]
    coordinator: PetlibroCoordinator = data["coordinator"]

    entities = [
        PetlibroGrainOutputEvent(entry, topics, coordinator),
    ]
    async_add_entities(entities)


class PetlibroGrainOutputEvent(PetlibroBaseEntity, EventEntity):
    """Event entity for grain output (food dispensed)."""

    _attr_translation_key = "grain_dispensed"
    _attr_icon = "mdi:shaker-outline"
    _attr_event_types = ["grain_dispensed"]

    def __init__(
        self,
        entry: ConfigEntry,
        topics: dict[str, str],
        coordinator: PetlibroCoordinator,
    ) -> None:
        """Initialize the grain output event."""
        super().__init__(entry, topics)
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry.data[CONF_SERIAL]}_grain_output_event"
        self._unsubscribe: Callable[[], None] | None = None
        self._last_grain_num: int | None = None
        self._total_dispensed: int = 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "last_portions_dispensed": self._last_grain_num,
            "total_dispensed_session": self._total_dispensed,
        }

    @callback
    def _handle_event(self, payload: dict[str, Any]) -> None:
        """Handle event messages from coordinator."""
        cmd = payload.get("cmd")

        if cmd == CMD_GRAIN_OUTPUT:
            grain_num = payload.get("grainNum", 0)
            self._last_grain_num = grain_num
            self._total_dispensed += grain_num

            self._trigger_event(
                "grain_dispensed",
                {
                    "portions": grain_num,
                    "timestamp": payload.get("ts"),
                    "message_id": payload.get("msgId"),
                },
            )
            _LOGGER.debug(
                "Grain output event: %d portion(s) dispensed",
                grain_num,
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

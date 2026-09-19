"""Event platform for Petlibro Local integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.event import EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CMD_GRAIN_OUTPUT,
    CONF_SERIAL,
    DOMAIN,
    GRAIN_STEP_END,
)
from .coordinator import PetlibroCoordinator
from .entity import PetlibroDeviceEntity

_LOGGER = logging.getLogger(__name__)

EVENT_GRAIN_DISPENSED = "grain_dispensed"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Petlibro Local events from a config entry."""
    coordinator: PetlibroCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    async_add_entities([PetlibroGrainOutputEvent(entry, coordinator)])


class PetlibroGrainOutputEvent(PetlibroDeviceEntity, EventEntity):
    """Event entity for grain output (food dispensed).

    GRAIN_OUTPUT_EVENT arrives twice per dispense, once at GRAIN_START with
    actualGrainNum 0 and again ~10s later at GRAIN_END with the real figure.
    Only GRAIN_END fires the event, so a trigger sees one event per feed and
    the portion count is the amount that actually came out.
    """

    _attr_translation_key = "grain_dispensed"
    _attr_event_types = [EVENT_GRAIN_DISPENSED]

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: PetlibroCoordinator,
    ) -> None:
        """Initialize the grain output event."""
        super().__init__(entry, coordinator)
        self._attr_unique_id = f"{entry.data[CONF_SERIAL]}_grain_output_event"
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
        """Fire on the end of a dispense."""
        if payload.get("cmd") != CMD_GRAIN_OUTPUT:
            return
        if payload.get("execStep") != GRAIN_STEP_END:
            return

        # The event reports actualGrainNum / expectGrainNum. There is no
        # "grainNum" key here -- that is the field on the outbound
        # MANUAL_FEEDING_SERVICE command.
        actual = payload.get("actualGrainNum", 0)
        expected = payload.get("expectGrainNum")

        self._last_grain_num = actual
        self._total_dispensed += actual

        self._trigger_event(
            EVENT_GRAIN_DISPENSED,
            {
                "portions": actual,
                "expected_portions": expected,
                # A short feed means the hopper jammed or ran empty.
                "short_fed": expected is not None and actual < expected,
                # 1 = scheduled (on-device plan), 2 = manual.
                "feed_type": payload.get("type"),
                "plan_id": payload.get("planId"),
                "timestamp": payload.get("ts"),
                "message_id": payload.get("msgId"),
            },
        )
        self.async_write_ha_state()

        _LOGGER.debug(
            "Grain output event: %s of %s portion(s) dispensed", actual, expected
        )

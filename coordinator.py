"""Coordinator for the Petlibro Local integration."""
from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback

from .const import CMD_ATTR_GET, CMD_HEARTBEAT
from .helpers import publish_command

_LOGGER = logging.getLogger(__name__)


class PetlibroCoordinator:
    """Coordinator for managing shared MQTT subscriptions.

    This class handles subscribing to MQTT topics once and dispatching
    messages to all registered listeners, avoiding duplicate subscriptions
    and redundant JSON parsing.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        topics: dict[str, str],
    ) -> None:
        """Initialize the coordinator.

        Args:
            hass: Home Assistant instance.
            entry: Config entry for this device.
            topics: Dictionary of MQTT topics.
        """
        self.hass = hass
        self.entry = entry
        self.topics = topics
        self._event_listeners: list[Callable[[dict[str, Any]], None]] = []
        self._heartbeat_listeners: list[Callable[[dict[str, Any]], None]] = []
        self._unsubscribe_event: Callable[[], None] | None = None
        self._unsubscribe_heartbeat: Callable[[], None] | None = None
        self._state_requested: bool = False
        self._device_state: dict[str, Any] = {}

    @property
    def device_state(self) -> dict[str, Any]:
        """Return the current device state."""
        return self._device_state

    def register_event_listener(
        self, listener: Callable[[dict[str, Any]], None]
    ) -> Callable[[], None]:
        """Register a listener for event messages.

        Args:
            listener: Callback function that receives parsed payload.

        Returns:
            Unsubscribe function.
        """
        self._event_listeners.append(listener)

        def unsubscribe() -> None:
            if listener in self._event_listeners:
                self._event_listeners.remove(listener)

        return unsubscribe

    def register_heartbeat_listener(
        self, listener: Callable[[dict[str, Any]], None]
    ) -> Callable[[], None]:
        """Register a listener for heartbeat messages.

        Args:
            listener: Callback function that receives parsed payload.

        Returns:
            Unsubscribe function.
        """
        self._heartbeat_listeners.append(listener)

        def unsubscribe() -> None:
            if listener in self._heartbeat_listeners:
                self._heartbeat_listeners.remove(listener)

        return unsubscribe

    async def async_setup(self) -> None:
        """Set up the coordinator and subscribe to MQTT topics."""

        @callback
        def event_received(msg: mqtt.ReceiveMessage) -> None:
            """Handle event messages."""
            try:
                payload = json.loads(msg.payload)
                # Update device state cache
                self._device_state.update(payload)
                # Dispatch to all listeners
                for listener in self._event_listeners:
                    listener(payload)
            except json.JSONDecodeError:
                _LOGGER.warning("Invalid JSON in MQTT event message: %s", msg.payload)

        @callback
        def heartbeat_received(msg: mqtt.ReceiveMessage) -> None:
            """Handle heartbeat messages."""
            try:
                payload = json.loads(msg.payload)
                if payload.get("cmd") == CMD_HEARTBEAT:
                    # Request state once if we haven't yet
                    if not self._state_requested:
                        self._state_requested = True
                        self.hass.async_create_task(self.async_request_state())
                    # Dispatch to all listeners
                    for listener in self._heartbeat_listeners:
                        listener(payload)
            except json.JSONDecodeError:
                pass

        self._unsubscribe_event = await mqtt.async_subscribe(
            self.hass,
            self.topics["event"],
            event_received,
            qos=0,
        )

        self._unsubscribe_heartbeat = await mqtt.async_subscribe(
            self.hass,
            self.topics["heartbeat"],
            heartbeat_received,
            qos=0,
        )

        # Request initial state
        await self.async_request_state()

    async def async_unload(self) -> None:
        """Unsubscribe from MQTT topics."""
        if self._unsubscribe_event:
            self._unsubscribe_event()
        if self._unsubscribe_heartbeat:
            self._unsubscribe_heartbeat()

    async def async_request_state(self) -> None:
        """Request current device state (once for all entities)."""
        await publish_command(
            self.hass,
            self.topics["command"],
            CMD_ATTR_GET,
        )
        _LOGGER.debug("Requested device state")

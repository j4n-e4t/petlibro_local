"""Switch platform for Petlibro Local integration."""
from __future__ import annotations

import json
import logging
import uuid
from abc import abstractmethod
from datetime import datetime
from typing import Any

from homeassistant.components import mqtt
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CMD_ATTR_GET,
    CMD_ATTR_PUSH,
    CMD_ATTR_SET,
    CMD_HEARTBEAT,
    CONF_MODEL,
    CONF_SERIAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Petlibro Local switches from a config entry."""
    topics = hass.data[DOMAIN][entry.entry_id]["topics"]

    # Create shared state dict for all entities
    hass.data[DOMAIN][entry.entry_id]["state"] = {}

    entities = [
        PetlibroChildLockSwitch(hass, entry, topics),
        PetlibroSoundSwitch(hass, entry, topics),
    ]
    async_add_entities(entities)


class PetlibroBaseSwitch(SwitchEntity):
    """Base class for Petlibro switches."""

    _attr_has_entity_name = True
    _state_key: str  # Key in payload to read state from

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        topics: dict[str, str],
    ) -> None:
        """Initialize the switch."""
        self.hass = hass
        self._entry = entry
        self._command_topic = topics["command"]
        self._event_topic = topics["event"]
        self._heartbeat_topic = topics["heartbeat"]
        self._is_on: bool | None = None
        self._unsubscribe_event: callable | None = None
        self._unsubscribe_heartbeat: callable | None = None

    @property
    def is_on(self) -> bool | None:
        """Return true if switch is on."""
        return self._is_on

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._is_on is not None

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device info."""
        data = self._entry.data
        return {
            "identifiers": {(DOMAIN, data[CONF_SERIAL])},
            "name": data.get(CONF_NAME) or f"Petlibro {data[CONF_MODEL]} {data[CONF_SERIAL]}",
            "manufacturer": "Petlibro",
            "model": data[CONF_MODEL],
            "serial_number": data[CONF_SERIAL],
        }

    async def async_added_to_hass(self) -> None:
        """Subscribe to MQTT events when added to hass."""
        @callback
        def event_received(msg: mqtt.ReceiveMessage) -> None:
            """Handle event messages."""
            try:
                payload = json.loads(msg.payload)
                cmd = payload.get("cmd")

                if cmd in (CMD_ATTR_GET, CMD_ATTR_PUSH) and self._state_key in payload:
                    self._is_on = payload[self._state_key]
                    self.async_write_ha_state()
                    _LOGGER.debug(
                        "%s state updated to %s (from %s)",
                        self._attr_name,
                        self._is_on,
                        cmd,
                    )

            except json.JSONDecodeError:
                _LOGGER.warning("Invalid JSON in MQTT message: %s", msg.payload)

        @callback
        def heartbeat_received(msg: mqtt.ReceiveMessage) -> None:
            """Handle heartbeat messages - request state if we don't have it."""
            try:
                payload = json.loads(msg.payload)
                if payload.get("cmd") == CMD_HEARTBEAT:
                    if self._is_on is None:
                        self.hass.async_create_task(self._request_state())
            except json.JSONDecodeError:
                pass

        self._unsubscribe_event = await mqtt.async_subscribe(
            self.hass,
            self._event_topic,
            event_received,
            qos=0,
        )

        self._unsubscribe_heartbeat = await mqtt.async_subscribe(
            self.hass,
            self._heartbeat_topic,
            heartbeat_received,
            qos=0,
        )

        await self._request_state()

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from MQTT when removed."""
        if self._unsubscribe_event:
            self._unsubscribe_event()
        if self._unsubscribe_heartbeat:
            self._unsubscribe_heartbeat()

    async def _request_state(self) -> None:
        """Request current device state."""
        msg_id = str(uuid.uuid4())
        ts = int(datetime.now().timestamp() * 1000)

        payload = {
            "cmd": CMD_ATTR_GET,
            "ts": ts,
            "msgId": msg_id,
        }

        await mqtt.async_publish(
            self.hass,
            self._command_topic,
            json.dumps(payload),
            qos=0,
            retain=False,
        )

    @abstractmethod
    def _get_command_payload(self, state: bool) -> dict[str, Any]:
        """Get the payload for setting state."""

    async def _send_command(self, state: bool) -> None:
        """Send the command to set state."""
        msg_id = str(uuid.uuid4())
        ts = int(datetime.now().timestamp() * 1000)

        payload = {
            "cmd": CMD_ATTR_SET,
            **self._get_command_payload(state),
            "ts": ts,
            "msgId": msg_id,
        }

        await mqtt.async_publish(
            self.hass,
            self._command_topic,
            json.dumps(payload),
            qos=0,
            retain=False,
        )

        _LOGGER.debug("Published to %s: %s", self._command_topic, payload)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._send_command(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._send_command(False)


class PetlibroChildLockSwitch(PetlibroBaseSwitch):
    """Representation of the Petlibro hardware button lock switch."""

    _attr_name = "Hardware Button Lock"
    _attr_icon = "mdi:lock"
    _state_key = "disableHardwareButton"

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        topics: dict[str, str],
    ) -> None:
        """Initialize the hardware button lock switch."""
        super().__init__(hass, entry, topics)
        self._attr_unique_id = f"{entry.data[CONF_SERIAL]}_hardware_button_lock"

    def _get_command_payload(self, state: bool) -> dict[str, Any]:
        """Get the payload for setting hardware button lock state."""
        return {
            "disableHardwareButton": state,
            "filterLedSwitch": state,
        }


class PetlibroSoundSwitch(PetlibroBaseSwitch):
    """Representation of the Petlibro sound switch."""

    _attr_name = "Sound"
    _attr_icon = "mdi:volume-high"
    _state_key = "soundSwitch"

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        topics: dict[str, str],
    ) -> None:
        """Initialize the sound switch."""
        super().__init__(hass, entry, topics)
        self._attr_unique_id = f"{entry.data[CONF_SERIAL]}_sound"

    def _get_command_payload(self, state: bool) -> dict[str, Any]:
        """Get the payload for setting sound state."""
        return {
            "soundSwitch": state,
            "soundAgingType": 1,
        }

"""Switch platform for Petlibro Local integration."""
from __future__ import annotations

import logging
from abc import abstractmethod
from collections.abc import Callable
from typing import Any

from homeassistant.components.switch import SwitchEntity
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
    """Set up Petlibro Local switches from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    topics = data["topics"]
    coordinator: PetlibroCoordinator = data["coordinator"]

    entities = [
        PetlibroChildLockSwitch(entry, topics, coordinator),
        PetlibroSoundSwitch(entry, topics, coordinator),
    ]
    async_add_entities(entities)


class PetlibroBaseSwitch(PetlibroBaseEntity, SwitchEntity):
    """Base class for Petlibro switches."""

    _state_key: str  # Key in payload to read state from
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        entry: ConfigEntry,
        topics: dict[str, str],
        coordinator: PetlibroCoordinator,
    ) -> None:
        """Initialize the switch."""
        super().__init__(entry, topics)
        self._coordinator = coordinator
        self._is_on: bool | None = None
        self._unsubscribe: Callable[[], None] | None = None

    @property
    def is_on(self) -> bool | None:
        """Return true if switch is on."""
        return self._is_on

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._is_on is not None

    @callback
    def _handle_event(self, payload: dict[str, Any]) -> None:
        """Handle event messages from coordinator."""
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

    async def async_added_to_hass(self) -> None:
        """Register with coordinator when added to hass."""
        self._unsubscribe = self._coordinator.register_event_listener(
            self._handle_event
        )

    async def async_will_remove_from_hass(self) -> None:
        """Unregister from coordinator when removed."""
        if self._unsubscribe:
            self._unsubscribe()

    @abstractmethod
    def _get_command_payload(self, state: bool) -> dict[str, Any]:
        """Get the payload for setting state."""

    async def _send_command(self, state: bool) -> None:
        """Send the command to set state."""
        await publish_command(
            self.hass,
            self._command_topic,
            CMD_ATTR_SET,
            **self._get_command_payload(state),
        )

        _LOGGER.debug("Sent %s command for %s", state, self._attr_name)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._send_command(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._send_command(False)


class PetlibroChildLockSwitch(PetlibroBaseSwitch):
    """Representation of the Petlibro hardware button lock switch."""

    _attr_translation_key = "hardware_button_lock"
    _attr_icon = "mdi:lock"
    _state_key = "disableHardwareButton"

    def __init__(
        self,
        entry: ConfigEntry,
        topics: dict[str, str],
        coordinator: PetlibroCoordinator,
    ) -> None:
        """Initialize the hardware button lock switch."""
        super().__init__(entry, topics, coordinator)
        self._attr_unique_id = f"{entry.data[CONF_SERIAL]}_hardware_button_lock"

    def _get_command_payload(self, state: bool) -> dict[str, Any]:
        """Get the payload for setting hardware button lock state."""
        return {
            "disableHardwareButton": state,
            "filterLedSwitch": state,
        }


class PetlibroSoundSwitch(PetlibroBaseSwitch):
    """Representation of the Petlibro sound switch."""

    _attr_translation_key = "sound"
    _attr_icon = "mdi:volume-high"
    _state_key = "soundSwitch"

    def __init__(
        self,
        entry: ConfigEntry,
        topics: dict[str, str],
        coordinator: PetlibroCoordinator,
    ) -> None:
        """Initialize the sound switch."""
        super().__init__(entry, topics, coordinator)
        self._attr_unique_id = f"{entry.data[CONF_SERIAL]}_sound"

    def _get_command_payload(self, state: bool) -> dict[str, Any]:
        """Get the payload for setting sound state."""
        return {
            "soundSwitch": state,
            "soundAgingType": 1,
        }

"""Switch platform for Petlibro Local integration."""
from __future__ import annotations

import logging
from abc import abstractmethod
from typing import Any

from homeassistant.components.switch import SwitchEntity
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
    """Set up Petlibro Local switches from a config entry."""
    coordinator: PetlibroCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    async_add_entities(
        [
            PetlibroChildLockSwitch(entry, coordinator),
            PetlibroSoundSwitch(entry, coordinator),
        ]
    )


class PetlibroBaseSwitch(PetlibroAttributeEntity, SwitchEntity):
    """Base class for Petlibro switches."""

    _attr_entity_category = EntityCategory.CONFIG

    @property
    def is_on(self) -> bool | None:
        """Return true if switch is on."""
        return self._is_on

    @abstractmethod
    def _get_command_payload(self, state: bool) -> dict[str, Any]:
        """Get the payload for setting state."""

    async def _send_command(self, state: bool) -> None:
        """Set the state, then wait for the device to confirm.

        async_send_command raises if the device does not ack, so a command that
        never reaches the feeder surfaces as an error in the UI instead of a
        toggle that silently springs back.
        """
        await self._coordinator.async_send_command(
            CMD_ATTR_SET, **self._get_command_payload(state)
        )

        # Optimistic: the device acked, and the resulting ATTR_PUSH_EVENT will
        # confirm or correct this within a few hundred milliseconds.
        self._is_on = state
        self.async_write_ha_state()
        _LOGGER.debug("%s set to %s and acked", self.entity_id, state)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._send_command(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._send_command(False)


class PetlibroChildLockSwitch(PetlibroBaseSwitch):
    """The physical button lock (child lock) on the feeder.

    On means the buttons on the device are disabled.
    """

    _attr_translation_key = "hardware_button_lock"
    _state_key = "disableHardwareButton"

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: PetlibroCoordinator,
    ) -> None:
        """Initialize the hardware button lock switch."""
        super().__init__(entry, coordinator)
        self._attr_unique_id = f"{entry.data[CONF_SERIAL]}_hardware_button_lock"

    def _get_command_payload(self, state: bool) -> dict[str, Any]:
        """Get the payload for setting hardware button lock state.

        filterLedSwitch is true in every ATTR_SET_SERVICE the vendor app was
        ever captured sending, including the ones that turn something off. It
        is a flag on the set operation, not a device attribute -- it never
        comes back in ATTR_PUSH_EVENT. Sending false here (it used to track
        `state`) is off-protocol, and unlocking was the case that hit it.
        """
        return {
            "disableHardwareButton": state,
            "filterLedSwitch": True,
        }


class PetlibroSoundSwitch(PetlibroBaseSwitch):
    """Representation of the Petlibro sound switch."""

    _attr_translation_key = "sound"
    _state_key = "soundSwitch"

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: PetlibroCoordinator,
    ) -> None:
        """Initialize the sound switch."""
        super().__init__(entry, coordinator)
        self._attr_unique_id = f"{entry.data[CONF_SERIAL]}_sound"

    def _get_command_payload(self, state: bool) -> dict[str, Any]:
        """Get the payload for setting sound state."""
        return {
            "soundSwitch": state,
            "soundAgingType": 1,
            "filterLedSwitch": True,
        }

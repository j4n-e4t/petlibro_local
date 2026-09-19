"""Base entities for the Petlibro Local integration."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import CMD_ATTR_GET, CMD_ATTR_PUSH, CONF_MODEL, CONF_SERIAL, DOMAIN
from .coordinator import PetlibroCoordinator


class PetlibroBaseEntity(Entity):
    """Base class for all Petlibro entities."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: PetlibroCoordinator,
    ) -> None:
        """Initialize the base entity.

        Args:
            entry: Config entry for this device.
            coordinator: Shared coordinator for this device.
        """
        self._entry = entry
        self._coordinator = coordinator
        self._command_topic = coordinator.topics["command"]
        self._unsubscribes: list[Callable[[], None]] = []

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        data = self._entry.data
        return DeviceInfo(
            identifiers={(DOMAIN, data[CONF_SERIAL])},
            name=data.get(CONF_NAME) or f"Petlibro {data[CONF_MODEL]} {data[CONF_SERIAL]}",
            manufacturer="Petlibro",
            model=data[CONF_MODEL],
            serial_number=data[CONF_SERIAL],
        )

    async def async_will_remove_from_hass(self) -> None:
        """Drop every coordinator subscription."""
        for unsubscribe in self._unsubscribes:
            unsubscribe()
        self._unsubscribes.clear()
        # ButtonEntity, EventEntity and DateTimeEntity sit further along the
        # MRO on RestoreEntity, which hooks this to save state.
        await super().async_will_remove_from_hass()


class PetlibroDeviceEntity(PetlibroBaseEntity):
    """Base class for entities that mirror live device state.

    These follow the device's availability: if the feeder stops heartbeating,
    they go unavailable rather than showing a stale value that cannot be
    changed.
    """

    @property
    def available(self) -> bool:
        """Return True while the device is reachable."""
        return self._coordinator.available

    async def async_added_to_hass(self) -> None:
        """Subscribe to device events and availability changes."""
        await super().async_added_to_hass()
        self._unsubscribes.append(
            self._coordinator.register_event_listener(self._handle_event)
        )
        self._unsubscribes.append(
            self._coordinator.register_availability_listener(
                self._handle_availability
            )
        )

    @callback
    def _handle_event(self, payload: dict[str, Any]) -> None:
        """Handle an event message from the coordinator."""

    @callback
    def _handle_availability(self, _available: bool) -> None:
        """Re-render when the device appears or goes quiet."""
        self.async_write_ha_state()


class PetlibroAttributeEntity(PetlibroDeviceEntity):
    """Base class for entities backed by a single ATTR_PUSH_EVENT key."""

    _state_key: str

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: PetlibroCoordinator,
    ) -> None:
        """Initialize the attribute-backed entity."""
        super().__init__(entry, coordinator)
        # Seed from the coordinator's cache so an entity added after the
        # device's boot push does not start out unknown.
        self._is_on: bool | None = coordinator.device_state.get(self._state_key)

    @callback
    def _handle_event(self, payload: dict[str, Any]) -> None:
        """Track our own key out of full and partial attribute pushes.

        ATTR_PUSH_EVENT carries only the keys that changed, so the membership
        test matters: reading payload.get(key) would reset the entity to None
        on every unrelated update.
        """
        if payload.get("cmd") not in (CMD_ATTR_GET, CMD_ATTR_PUSH):
            return
        if self._state_key not in payload:
            return

        self._is_on = payload[self._state_key]
        self.async_write_ha_state()

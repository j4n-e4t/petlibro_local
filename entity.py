"""Base entity for the Petlibro Local integration."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import CONF_MODEL, CONF_SERIAL, DOMAIN


class PetlibroBaseEntity(Entity):
    """Base class for all Petlibro entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: ConfigEntry,
        topics: dict[str, str],
    ) -> None:
        """Initialize the base entity.

        Args:
            entry: Config entry for this device.
            topics: Dictionary of MQTT topics.
        """
        self._entry = entry
        self._command_topic = topics["command"]
        self._event_topic = topics["event"]
        self._heartbeat_topic = topics["heartbeat"]

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

"""Button platform for Petlibro Local integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CMD_DEVICE_REBOOT,
    CMD_MANUAL_FEEDING,
    CONF_SERIAL,
    DOMAIN,
)
from .entity import PetlibroBaseEntity
from .helpers import publish_command

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Petlibro Local buttons from a config entry."""
    topics = hass.data[DOMAIN][entry.entry_id]["topics"]

    entities = [
        PetlibroFeedButton(entry, topics),
        PetlibroRebootButton(entry, topics),
    ]
    async_add_entities(entities)


class PetlibroFeedButton(PetlibroBaseEntity, ButtonEntity):
    """Button that triggers a manual feeding with 1 portion."""

    _attr_name = "Feed"
    _attr_icon = "mdi:food-drumstick"

    def __init__(
        self,
        entry: ConfigEntry,
        topics: dict[str, str],
    ) -> None:
        """Initialize the button."""
        super().__init__(entry, topics)
        self._attr_unique_id = f"{entry.data[CONF_SERIAL]}_feed_button"

    async def async_press(self) -> None:
        """Handle the button press - trigger manual feeding with 1 portion."""
        await publish_command(
            self.hass,
            self._command_topic,
            CMD_MANUAL_FEEDING,
            grainNum=1,
        )

        _LOGGER.debug("Feed button pressed - dispensing 1 portion")


class PetlibroRebootButton(PetlibroBaseEntity, ButtonEntity):
    """Button that triggers a device reboot."""

    _attr_name = "Reboot Device"
    _attr_icon = "mdi:restart"
    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        entry: ConfigEntry,
        topics: dict[str, str],
    ) -> None:
        """Initialize the reboot button."""
        super().__init__(entry, topics)
        self._attr_unique_id = f"{entry.data[CONF_SERIAL]}_reboot_button"

    async def async_press(self) -> None:
        """Handle the button press - trigger device reboot."""
        await publish_command(
            self.hass,
            self._command_topic,
            CMD_DEVICE_REBOOT,
        )

        _LOGGER.debug("Reboot button pressed - sending reboot command")

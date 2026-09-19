"""Button platform for Petlibro Local integration."""
from __future__ import annotations

import logging

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import (
    CMD_DEVICE_REBOOT,
    CMD_MANUAL_FEEDING,
    CONF_SERIAL,
    DOMAIN,
    MAINTENANCE_LAST_CLEANED,
    MAINTENANCE_LAST_REFILL,
)
from .coordinator import PetlibroCoordinator
from .entity import PetlibroBaseEntity, PetlibroDeviceEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Petlibro Local buttons from a config entry."""
    coordinator: PetlibroCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    async_add_entities(
        [
            PetlibroFeedButton(entry, coordinator),
            PetlibroRebootButton(entry, coordinator),
            PetlibroMaintenanceButton(
                entry,
                coordinator,
                key=MAINTENANCE_LAST_CLEANED,
                translation_key="mark_cleaned",
            ),
            PetlibroMaintenanceButton(
                entry,
                coordinator,
                key=MAINTENANCE_LAST_REFILL,
                translation_key="mark_refilled",
            ),
        ]
    )


class PetlibroFeedButton(PetlibroDeviceEntity, ButtonEntity):
    """Button that triggers a manual feeding with 1 portion."""

    _attr_translation_key = "feed"

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: PetlibroCoordinator,
    ) -> None:
        """Initialize the button."""
        super().__init__(entry, coordinator)
        self._attr_unique_id = f"{entry.data[CONF_SERIAL]}_feed_button"

    async def async_press(self) -> None:
        """Handle the button press - trigger manual feeding with 1 portion."""
        await self._coordinator.async_send_command(CMD_MANUAL_FEEDING, grainNum=1)
        _LOGGER.debug("Feed button pressed - dispensing 1 portion")


class PetlibroRebootButton(PetlibroDeviceEntity, ButtonEntity):
    """Button that triggers a device reboot."""

    _attr_translation_key = "reboot"
    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: PetlibroCoordinator,
    ) -> None:
        """Initialize the reboot button."""
        super().__init__(entry, coordinator)
        self._attr_unique_id = f"{entry.data[CONF_SERIAL]}_reboot_button"

    async def async_press(self) -> None:
        """Handle the button press - trigger device reboot.

        DEVICE_REBOOT has never been seen on the wire and a rebooting device
        cannot ack anyway, so this one is fire and forget.
        """
        await self._coordinator.async_send_command(
            CMD_DEVICE_REBOOT, expect_ack=False
        )
        _LOGGER.debug("Reboot button pressed - sending reboot command")


class PetlibroMaintenanceButton(PetlibroBaseEntity, ButtonEntity):
    """Button that stamps a maintenance timestamp with the current time."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: PetlibroCoordinator,
        key: str,
        translation_key: str,
    ) -> None:
        """Initialize the maintenance button.

        Args:
            entry: Config entry for this device.
            coordinator: Shared coordinator, which holds the timestamp.
            key: Maintenance key this button stamps.
            translation_key: Entity name translation key.
        """
        super().__init__(entry, coordinator)
        self._key = key
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{entry.data[CONF_SERIAL]}_{key}_button"

    @property
    def available(self) -> bool:
        """Return True always - this records nothing on the device."""
        return True

    async def async_press(self) -> None:
        """Set the matching timestamp to now."""
        self._coordinator.set_maintenance(self._key, dt_util.utcnow())

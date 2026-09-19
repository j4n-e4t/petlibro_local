"""Sensor platform for Petlibro Local integration.

The feeder reports nothing about when it was last cleaned or refilled, so
these two timestamps are Home Assistant side bookkeeping. They are read-only:
the only thing that moves them is a press of the matching button, which stamps
the current time.
"""
from __future__ import annotations

import logging
from datetime import datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from .const import (
    CONF_SERIAL,
    DOMAIN,
    MAINTENANCE_LAST_CLEANED,
    MAINTENANCE_LAST_REFILL,
)
from .coordinator import PetlibroCoordinator
from .entity import PetlibroBaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Petlibro Local maintenance timestamps from a config entry."""
    coordinator: PetlibroCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    async_add_entities(
        [
            PetlibroMaintenanceSensor(
                entry,
                coordinator,
                key=MAINTENANCE_LAST_CLEANED,
                translation_key="last_cleaned",
            ),
            PetlibroMaintenanceSensor(
                entry,
                coordinator,
                key=MAINTENANCE_LAST_REFILL,
                translation_key="last_refill",
            ),
        ]
    )


class PetlibroMaintenanceSensor(PetlibroBaseEntity, SensorEntity, RestoreEntity):
    """A maintenance timestamp kept by Home Assistant.

    Read-only: it is written by its companion button and by nothing else. The
    timestamp device class is what makes the frontend render it as "3 days
    ago" rather than as a date, which is the form the question usually takes.
    """

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: PetlibroCoordinator,
        key: str,
        translation_key: str,
    ) -> None:
        """Initialize the maintenance timestamp.

        Args:
            entry: Config entry for this device.
            coordinator: Shared coordinator, which holds the value.
            key: Maintenance key this entity renders.
            translation_key: Entity name translation key.
        """
        super().__init__(entry, coordinator)
        self._key = key
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{entry.data[CONF_SERIAL]}_{key}"

    @property
    def available(self) -> bool:
        """Return True always.

        This is our own bookkeeping, not device state, so it keeps showing the
        last known timestamp while the feeder is offline.
        """
        return True

    @property
    def native_value(self) -> datetime | None:
        """Return the timestamp, or None if it was never recorded."""
        return self._coordinator.get_maintenance(self._key)

    async def async_added_to_hass(self) -> None:
        """Restore the timestamp and follow coordinator updates."""
        await super().async_added_to_hass()

        if self._coordinator.get_maintenance(self._key) is None:
            if (restored := await self._async_restored_value()) is not None:
                self._coordinator.set_maintenance(self._key, restored)

        self._unsubscribes.append(
            self._coordinator.register_maintenance_listener(
                self._key, self._handle_update
            )
        )

    async def _async_restored_value(self) -> datetime | None:
        """Read the timestamp back from the previous Home Assistant run."""
        last_state = await self.async_get_last_state()
        if last_state is None or last_state.state in (
            STATE_UNKNOWN,
            STATE_UNAVAILABLE,
        ):
            return None

        restored = dt_util.parse_datetime(last_state.state)
        if restored is None:
            _LOGGER.debug(
                "Could not restore %s from %s", self._key, last_state.state
            )
            return None

        return dt_util.as_utc(restored)

    @callback
    def _handle_update(self, _value: datetime | None) -> None:
        """Re-render when its button stamps a new time."""
        self.async_write_ha_state()

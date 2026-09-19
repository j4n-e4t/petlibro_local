"""Date/time platform for Petlibro Local integration.

The feeder reports nothing about when it was last cleaned or refilled, so
these two timestamps are Home Assistant side bookkeeping. They are writable
DateTimeEntities rather than read-only sensors so a wrong entry can be
corrected without editing an automation, and each has a companion button that
stamps "now".
"""
from __future__ import annotations

import logging
from datetime import datetime

from homeassistant.components.datetime import DateTimeEntity
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
            PetlibroMaintenanceDateTime(
                entry,
                coordinator,
                key=MAINTENANCE_LAST_CLEANED,
                translation_key="last_cleaned",
            ),
            PetlibroMaintenanceDateTime(
                entry,
                coordinator,
                key=MAINTENANCE_LAST_REFILL,
                translation_key="last_refill",
            ),
        ]
    )


class PetlibroMaintenanceDateTime(PetlibroBaseEntity, DateTimeEntity, RestoreEntity):
    """A maintenance timestamp kept by Home Assistant."""

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

        This is our own bookkeeping, not device state, so it stays usable while
        the feeder is offline.
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
        """Re-render when the value changes, including from its button."""
        self.async_write_ha_state()

    async def async_set_value(self, value: datetime) -> None:
        """Set the timestamp to a value picked by the user."""
        self._coordinator.set_maintenance(self._key, dt_util.as_utc(value))

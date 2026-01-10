"""Sensor platform for Petlibro Local integration."""
from __future__ import annotations

import json
import logging
from datetime import datetime

from homeassistant.components import mqtt
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import (
    CMD_MANUAL_FEEDING,
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
    """Set up Petlibro Local sensors from a config entry."""
    topics = hass.data[DOMAIN][entry.entry_id]["topics"]

    entities = [
        PetlibroLastFeedingSensor(hass, entry, topics),
        PetlibroDailyFeedingCountSensor(hass, entry, topics),
    ]
    async_add_entities(entities)


class PetlibroLastFeedingSensor(SensorEntity):
    """Sensor that tracks the last manual feeding timestamp."""

    _attr_has_entity_name = True
    _attr_name = "Last Feeding"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:clock-outline"

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        topics: dict[str, str],
    ) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self._entry = entry
        self._event_topic = topics["event"]
        self._attr_unique_id = f"{entry.data[CONF_SERIAL]}_last_feeding"
        self._attr_native_value: datetime | None = None
        self._unsubscribe_event: callable | None = None

    @property
    def device_info(self) -> dict[str, any]:
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

                if cmd == CMD_MANUAL_FEEDING:
                    # Update last feeding timestamp to now
                    self._attr_native_value = dt_util.now()
                    self.async_write_ha_state()
                    _LOGGER.info("Manual feeding event detected at %s", self._attr_native_value)

            except json.JSONDecodeError:
                _LOGGER.warning("Invalid JSON in MQTT message: %s", msg.payload)

        self._unsubscribe_event = await mqtt.async_subscribe(
            self.hass,
            self._event_topic,
            event_received,
            qos=0,
        )

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from MQTT when removed."""
        if self._unsubscribe_event:
            self._unsubscribe_event()


class PetlibroDailyFeedingCountSensor(SensorEntity):
    """Sensor that tracks the number of manual feedings today."""

    _attr_has_entity_name = True
    _attr_name = "Daily Feeding Count"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:counter"
    _attr_native_unit_of_measurement = "feedings"

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        topics: dict[str, str],
    ) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self._entry = entry
        self._event_topic = topics["event"]
        self._attr_unique_id = f"{entry.data[CONF_SERIAL]}_daily_feeding_count"
        self._attr_native_value = 0
        self._last_reset_date: datetime | None = None
        self._unsubscribe_event: callable | None = None

    @property
    def device_info(self) -> dict[str, any]:
        """Return device info."""
        data = self._entry.data
        return {
            "identifiers": {(DOMAIN, data[CONF_SERIAL])},
            "name": data.get(CONF_NAME) or f"Petlibro {data[CONF_MODEL]} {data[CONF_SERIAL]}",
            "manufacturer": "Petlibro",
            "model": data[CONF_MODEL],
            "serial_number": data[CONF_SERIAL],
        }

    @property
    def extra_state_attributes(self) -> dict[str, any]:
        """Return extra state attributes."""
        return {
            "last_reset": self._last_reset_date.isoformat() if self._last_reset_date else None,
        }

    def _check_and_reset_daily_count(self) -> None:
        """Reset the count if it's a new day."""
        now = dt_util.now()
        today = now.date()

        if self._last_reset_date is None or self._last_reset_date.date() != today:
            self._attr_native_value = 0
            self._last_reset_date = now
            _LOGGER.debug("Daily feeding count reset for new day: %s", today)

    async def async_added_to_hass(self) -> None:
        """Subscribe to MQTT events when added to hass."""
        # Initialize reset date to today
        self._last_reset_date = dt_util.now()

        @callback
        def event_received(msg: mqtt.ReceiveMessage) -> None:
            """Handle event messages."""
            try:
                payload = json.loads(msg.payload)
                cmd = payload.get("cmd")

                if cmd == CMD_MANUAL_FEEDING:
                    # Check if we need to reset the count for a new day
                    self._check_and_reset_daily_count()

                    # Increment the count
                    self._attr_native_value += 1
                    self.async_write_ha_state()
                    _LOGGER.info("Daily feeding count incremented to %d", self._attr_native_value)

            except json.JSONDecodeError:
                _LOGGER.warning("Invalid JSON in MQTT message: %s", msg.payload)

        self._unsubscribe_event = await mqtt.async_subscribe(
            self.hass,
            self._event_topic,
            event_received,
            qos=0,
        )

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from MQTT when removed."""
        if self._unsubscribe_event:
            self._unsubscribe_event()

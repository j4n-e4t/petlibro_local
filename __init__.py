"""The Petlibro Local integration."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr
import homeassistant.helpers.config_validation as cv

from .const import (
    ATTR_CMD,
    ATTR_PAYLOAD,
    ATTR_PORTIONS,
    CMD_MANUAL_FEEDING,
    CONF_MODEL,
    CONF_SERIAL,
    DOMAIN,
    PLATFORMS,
    SERVICE_FEED,
    SERVICE_SEND_COMMAND,
    get_topics,
)
from .coordinator import PetlibroCoordinator
from .helpers import PetlibroCommandError, publish_command

_LOGGER = logging.getLogger(__name__)


def _get_entry_from_device_id(
    hass: HomeAssistant, device_id: str
) -> tuple[ConfigEntry, dict] | tuple[None, None]:
    """Get the config entry and data for a device ID.

    Args:
        hass: Home Assistant instance.
        device_id: Device registry ID.

    Returns:
        Tuple of (ConfigEntry, entry_data) or (None, None) if not found.
    """
    device_registry = dr.async_get(hass)
    device = device_registry.async_get(device_id)
    if device is None:
        return None, None

    # Find the serial from device identifiers
    serial = None
    for identifier in device.identifiers:
        if identifier[0] == DOMAIN:
            serial = identifier[1]
            break

    if serial is None:
        return None, None

    # Find the entry by serial
    for entry_id, entry_data in hass.data.get(DOMAIN, {}).items():
        if entry_data["config"].get(CONF_SERIAL) == serial:
            entry = hass.config_entries.async_get_entry(entry_id)
            if entry:
                return entry, entry_data

    return None, None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Petlibro Local from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    model = entry.data[CONF_MODEL]
    serial = entry.data[CONF_SERIAL]
    topics = get_topics(model, serial)

    # Create and setup coordinator
    coordinator = PetlibroCoordinator(hass, entry, topics)
    await coordinator.async_setup()

    hass.data[DOMAIN][entry.entry_id] = {
        "config": entry.data,
        "topics": topics,
        "coordinator": coordinator,
    }

    # Register services only once (when first entry is loaded)
    if not hass.services.has_service(DOMAIN, SERVICE_SEND_COMMAND):
        _register_services(hass)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


def _register_services(hass: HomeAssistant) -> None:
    """Register integration services."""

    service_schema = vol.Schema(
        {
            vol.Required("device_id"): vol.Any(cv.string, [cv.string]),
            vol.Required(ATTR_CMD): cv.string,
            vol.Optional(ATTR_PAYLOAD, default={}): vol.Any(dict, None),
        }
    )

    feed_schema = vol.Schema(
        {
            vol.Required("device_id"): vol.Any(cv.string, [cv.string]),
            vol.Required(ATTR_PORTIONS): cv.positive_int,
        }
    )

    async def async_send_command(call: ServiceCall) -> None:
        """Handle the send_command service call."""
        cmd = call.data[ATTR_CMD]
        payload_data = call.data.get(ATTR_PAYLOAD, {}) or {}

        device_ids = call.data.get("device_id", [])
        if isinstance(device_ids, str):
            device_ids = [device_ids]

        if not device_ids:
            raise PetlibroCommandError("No device specified")

        for device_id in device_ids:
            entry, entry_data = _get_entry_from_device_id(hass, device_id)
            if entry is None:
                raise PetlibroCommandError(f"Device {device_id} not found")

            await publish_command(
                hass,
                entry_data["topics"]["command"],
                cmd,
                **payload_data,
            )

            _LOGGER.debug(
                "Sent command %s to device %s", cmd, entry.data[CONF_SERIAL]
            )

    async def async_feed(call: ServiceCall) -> None:
        """Handle the feed service call."""
        portions = call.data[ATTR_PORTIONS]

        device_ids = call.data.get("device_id", [])
        if isinstance(device_ids, str):
            device_ids = [device_ids]

        if not device_ids:
            raise PetlibroCommandError("No device specified")

        for device_id in device_ids:
            entry, entry_data = _get_entry_from_device_id(hass, device_id)
            if entry is None:
                raise PetlibroCommandError(f"Device {device_id} not found")

            await publish_command(
                hass,
                entry_data["topics"]["command"],
                CMD_MANUAL_FEEDING,
                grainNum=portions,
            )

            _LOGGER.info(
                "Manual feeding: %d portion(s) to device %s",
                portions,
                entry.data[CONF_SERIAL],
            )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_COMMAND,
        async_send_command,
        schema=service_schema,
        supports_response=False,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_FEED,
        async_feed,
        schema=feed_schema,
        supports_response=False,
    )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        # Unload coordinator
        coordinator: PetlibroCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
        await coordinator.async_unload()

        hass.data[DOMAIN].pop(entry.entry_id)

        # Only remove services if no more entries exist
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_SEND_COMMAND)
            hass.services.async_remove(DOMAIN, SERVICE_FEED)

    return unload_ok

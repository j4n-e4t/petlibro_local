"""The Petlibro Local integration."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
import homeassistant.helpers.config_validation as cv

from .const import (
    ATTR_CMD,
    ATTR_PAYLOAD,
    ATTR_PORTIONS,
    ATTR_WAIT_FOR_ACK,
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
from .helpers import PetlibroCommandError

_LOGGER = logging.getLogger(__name__)


def _get_coordinator(hass: HomeAssistant, device_id: str) -> PetlibroCoordinator:
    """Get the coordinator for a device registry ID.

    Args:
        hass: Home Assistant instance.
        device_id: Device registry ID.

    Returns:
        The coordinator handling that device.

    Raises:
        PetlibroCommandError: If the device is unknown or not loaded.
    """
    device_registry = dr.async_get(hass)
    device = device_registry.async_get(device_id)
    if device is None:
        raise PetlibroCommandError(f"Device {device_id} not found")

    serial = next(
        (
            identifier[1]
            for identifier in device.identifiers
            if identifier[0] == DOMAIN
        ),
        None,
    )
    if serial is None:
        raise PetlibroCommandError(
            f"Device {device_id} is not a Petlibro Local device"
        )

    for entry_data in hass.data.get(DOMAIN, {}).values():
        coordinator: PetlibroCoordinator = entry_data["coordinator"]
        if coordinator.entry.data[CONF_SERIAL] == serial:
            return coordinator

    raise PetlibroCommandError(f"Device {serial} is not loaded")


def _target_coordinators(
    hass: HomeAssistant, call: ServiceCall
) -> list[PetlibroCoordinator]:
    """Resolve a service call's device_id target to coordinators."""
    device_ids = call.data.get("device_id", [])
    if isinstance(device_ids, str):
        device_ids = [device_ids]

    if not device_ids:
        raise PetlibroCommandError("No device specified")

    return [_get_coordinator(hass, device_id) for device_id in device_ids]


@callback
def _async_remove_stale_entities(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Drop registry entries for platforms this integration no longer provides.

    Last cleaned / Last refill were DateTimeEntities in 0.2.0 and are read-only
    timestamp sensors from 0.3.0 on. Without this the old pair lingers in the
    registry as unavailable "restored" entities that nothing will ever write.
    """
    registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if entity.domain not in (platform.value for platform in PLATFORMS):
            registry.async_remove(entity.entity_id)
            _LOGGER.debug("Removed stale entity %s", entity.entity_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Petlibro Local from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    _async_remove_stale_entities(hass, entry)

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

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)


def _register_services(hass: HomeAssistant) -> None:
    """Register integration services."""

    service_schema = vol.Schema(
        {
            vol.Required("device_id"): vol.Any(cv.string, [cv.string]),
            vol.Required(ATTR_CMD): cv.string,
            vol.Optional(ATTR_PAYLOAD, default={}): vol.Any(dict, None),
            vol.Optional(ATTR_WAIT_FOR_ACK, default=True): cv.boolean,
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
        wait_for_ack = call.data[ATTR_WAIT_FOR_ACK]

        for coordinator in _target_coordinators(hass, call):
            await coordinator.async_send_command(
                cmd, expect_ack=wait_for_ack, **payload_data
            )

            _LOGGER.debug(
                "Sent command %s to device %s",
                cmd,
                coordinator.entry.data[CONF_SERIAL],
            )

    async def async_feed(call: ServiceCall) -> None:
        """Handle the feed service call."""
        portions = call.data[ATTR_PORTIONS]

        for coordinator in _target_coordinators(hass, call):
            await coordinator.async_send_command(
                CMD_MANUAL_FEEDING, grainNum=portions
            )

            _LOGGER.debug(
                "Manual feeding: %d portion(s) to device %s",
                portions,
                coordinator.entry.data[CONF_SERIAL],
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


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Remove a config entry from a device.

    Since each config entry represents a single device, removing the device
    means removing the entire config entry.
    """
    return True

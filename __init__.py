"""The Petlibro Local integration."""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime

import voluptuous as vol

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
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

_LOGGER = logging.getLogger(__name__)

SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CMD): cv.string,
        vol.Optional(ATTR_PAYLOAD, default={}): vol.Any(dict, None),
    }
)

FEED_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_PORTIONS): cv.positive_int,
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Petlibro Local from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    model = entry.data[CONF_MODEL]
    serial = entry.data[CONF_SERIAL]
    topics = get_topics(model, serial)

    hass.data[DOMAIN][entry.entry_id] = {
        "config": entry.data,
        "topics": topics,
    }

    command_topic = topics["command"]

    async def async_send_command(call: ServiceCall) -> None:
        """Handle the send_command service call."""
        cmd = call.data[ATTR_CMD]
        payload_data = call.data.get(ATTR_PAYLOAD, {}) or {}

        msg_id = str(uuid.uuid4())
        ts = int(datetime.now().timestamp() * 1000)

        final_payload = {
            "cmd": cmd,
            **payload_data,
            "ts": ts,
            "msgId": msg_id,
        }

        payload_json = json.dumps(final_payload)

        await mqtt.async_publish(
            hass,
            command_topic,
            payload_json,
            qos=0,
            retain=False,
        )

        _LOGGER.debug("Published to %s: %s", command_topic, payload_json)

    async def async_feed(call: ServiceCall) -> None:
        """Handle the feed service call."""
        portions = call.data[ATTR_PORTIONS]

        msg_id = str(uuid.uuid4())
        ts = int(datetime.now().timestamp() * 1000)

        final_payload = {
            "cmd": CMD_MANUAL_FEEDING,
            "grainNum": portions,
            "ts": ts,
            "msgId": msg_id,
        }

        payload_json = json.dumps(final_payload)

        await mqtt.async_publish(
            hass,
            command_topic,
            payload_json,
            qos=0,
            retain=False,
        )

        _LOGGER.info("Manual feeding: %d portion(s)", portions)
        _LOGGER.debug("Published to %s: %s", command_topic, payload_json)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_COMMAND,
        async_send_command,
        schema=SERVICE_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_FEED,
        async_feed,
        schema=FEED_SCHEMA,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.services.async_remove(DOMAIN, SERVICE_SEND_COMMAND)
        hass.services.async_remove(DOMAIN, SERVICE_FEED)
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok

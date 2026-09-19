"""Helper functions for the Petlibro Local integration."""
from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any

from homeassistant.components import mqtt
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)


class PetlibroCommandError(HomeAssistantError):
    """Error when sending a command to the Petlibro device."""


def new_msg_id() -> str:
    """Return a message ID in the format the vendor cloud uses.

    The cloud sends a UUID with the dashes stripped (32 hex characters). The
    device echoes whatever it is given, but a 36 character value with dashes is
    a format the firmware was never shipped against, so stay on the observed
    one.
    """
    return uuid.uuid4().hex


async def publish_payload(
    hass: HomeAssistant,
    topic: str,
    payload: dict[str, Any],
) -> None:
    """Publish a fully built JSON payload to the device.

    Args:
        hass: Home Assistant instance.
        topic: MQTT topic to publish to.
        payload: The payload to publish, serialized as-is.

    Raises:
        PetlibroCommandError: If the MQTT publish fails.
    """
    try:
        await mqtt.async_publish(
            hass,
            topic,
            json.dumps(payload),
            qos=0,
            retain=False,
        )
    except Exception as err:
        _LOGGER.error(
            "Failed to publish %s to %s: %s", payload.get("cmd"), topic, err
        )
        raise PetlibroCommandError(
            f"Failed to send {payload.get('cmd')} to device: {err}"
        ) from err


async def publish_command(
    hass: HomeAssistant,
    topic: str,
    cmd: str,
    msg_id: str | None = None,
    **kwargs: Any,
) -> str:
    """Publish a command to the Petlibro device.

    Automatically adds timestamp and message ID to the payload.

    Args:
        hass: Home Assistant instance.
        topic: MQTT topic to publish to.
        cmd: Command name.
        msg_id: Message ID to use; generated when omitted.
        **kwargs: Additional payload fields.

    Returns:
        The message ID the command was sent with, for correlating the ack.

    Raises:
        PetlibroCommandError: If the MQTT publish fails.
    """
    msg_id = msg_id or new_msg_id()
    payload = {
        "cmd": cmd,
        **kwargs,
        "ts": int(time.time() * 1000),
        "msgId": msg_id,
    }

    await publish_payload(hass, topic, payload)
    return msg_id

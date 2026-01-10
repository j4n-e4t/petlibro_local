"""Helper functions for the Petlibro Local integration."""
from __future__ import annotations

import json
import logging
import time
import uuid

from homeassistant.components import mqtt
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)


class PetlibroCommandError(HomeAssistantError):
    """Error when sending a command to the Petlibro device."""


async def publish_command(
    hass: HomeAssistant,
    topic: str,
    cmd: str,
    **kwargs,
) -> None:
    """Publish a command to the Petlibro device.

    Automatically adds timestamp and message ID to the payload.

    Args:
        hass: Home Assistant instance.
        topic: MQTT topic to publish to.
        cmd: Command name.
        **kwargs: Additional payload fields.

    Raises:
        PetlibroCommandError: If the MQTT publish fails.
    """
    payload = {
        "cmd": cmd,
        **kwargs,
        "ts": int(time.time() * 1000),
        "msgId": str(uuid.uuid4()),
    }

    try:
        await mqtt.async_publish(
            hass,
            topic,
            json.dumps(payload),
            qos=0,
            retain=False,
        )
    except Exception as err:
        _LOGGER.error("Failed to publish command %s to %s: %s", cmd, topic, err)
        raise PetlibroCommandError(
            f"Failed to send command {cmd} to device: {err}"
        ) from err

"""Constants for the Petlibro Local integration."""

from homeassistant.const import Platform

DOMAIN = "petlibro_local"

CONF_MODEL = "model"
CONF_SERIAL = "serial"

TOPIC_BASE = "dl/{model}/{serial}/device"
TOPIC_COMMAND_SUFFIX = "/service/sub"
TOPIC_EVENT_SUFFIX = "/event/post"
TOPIC_HEARTBEAT_SUFFIX = "/heart/post"

CMD_HEARTBEAT = "HEARTBEAT"


def get_topics(model: str, serial: str) -> dict[str, str]:
    """Build MQTT topics from model and serial."""
    base = TOPIC_BASE.format(model=model, serial=serial)
    return {
        "command": base + TOPIC_COMMAND_SUFFIX,
        "event": base + TOPIC_EVENT_SUFFIX,
        "heartbeat": base + TOPIC_HEARTBEAT_SUFFIX,
    }

SERVICE_SEND_COMMAND = "send_command"
SERVICE_FEED = "feed"
ATTR_CMD = "cmd"
ATTR_PAYLOAD = "payload"
ATTR_PORTIONS = "portions"

PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.EVENT,
    Platform.LIGHT,
    Platform.SWITCH,
]

CMD_ATTR_SET = "ATTR_SET_SERVICE"
CMD_ATTR_GET = "ATTR_GET_SERVICE"
CMD_ATTR_PUSH = "ATTR_PUSH_EVENT"
CMD_MANUAL_FEEDING = "MANUAL_FEEDING_SERVICE"
CMD_GRAIN_OUTPUT = "GRAIN_OUTPUT_EVENT"
CMD_DETECTION_EVENT = "DETECTION_EVENT"
CMD_DEVICE_REBOOT = "DEVICE_REBOOT"

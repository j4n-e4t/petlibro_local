"""Constants for the Petlibro Local integration."""

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

PLATFORMS = ["light", "sensor", "switch"]

CMD_ATTR_SET = "ATTR_SET_SERVICE"
CMD_ATTR_GET = "ATTR_GET_SERVICE"
CMD_ATTR_PUSH = "ATTR_PUSH_EVENT"
CMD_MANUAL_FEEDING = "MANUAL_FEEDING_SERVICE"

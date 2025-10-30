"""Constants for the Dali Center."""

from enum import Enum

# MQTT Topics
TOPIC_GATEWAY_PREFIX = "meribee/gateway"
TOPIC_PLATFORM_APP_PREFIX = "meribee/platform-app"

# Default values
DEFAULT_MQTT_PORT = 1883
DEFAULT_DISCOVERY_TIMEOUT = 30.0  # seconds

# SRLink Protocol Methods
METHOD_DEVICE_DISCOVER = "thing.subdev.getall"
METHOD_DEVICE_DISCOVER_REPLY = "thing.subdev.getall.reply"


class CallbackEventType(Enum):
    """Gateway callback event types for listener registration."""

    ONLINE_STATUS = "online_status"


class DeviceType(Enum):
    """Device type classification."""

    LIGHT = "light"

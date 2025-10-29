"""Constants for the Dali Center."""

from enum import Enum

# MQTT Topics
TOPIC_GATEWAY_PREFIX = "meribee/gateway"
TOPIC_PLATFORM_APP_PREFIX = "meribee/platform-app"

# Default values
DEFAULT_MQTT_PORT = 1883


class CallbackEventType(Enum):
    """Gateway callback event types for listener registration."""

    ONLINE_STATUS = "online_status"

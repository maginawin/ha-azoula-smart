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
METHOD_SERVICE_INVOKE = "thing.service"
METHOD_SERVICE_INVOKE_REPLY = "thing.service.reply"
METHOD_PROPERTY_POST = "thing.event.property.post"
METHOD_PROPERTY_GET = "thing.service.property.get"
METHOD_PROPERTY_GET_REPLY = "thing.service.property.get.reply"

# Property service identifiers
SERVICE_PROPERTY_GET = "get"

# Light service identifiers (Zigbee Cluster Services)
SERVICE_ONOFF_ON = "OnOffClusterOn"
SERVICE_ONOFF_OFF = "OnOffClusterOff"
SERVICE_ONOFF_TOGGLE = "OnOffClusterToggle"
SERVICE_LEVEL_MOVE_TO_LEVEL_WITH_ONOFF = "LevelControlClusterMoveToLevelWithOnOff"
SERVICE_COLOR_TEMP_MOVE_TO_COLOR_TEMP = "ControlClusterMoveToColorTemperature"
SERVICE_COLOR_MOVE_TO_COLOR = "ControlClusterMoveToColor"


class CallbackEventType(Enum):
    """Gateway callback event types for listener registration."""

    ONLINE_STATUS = "online_status"
    PROPERTY_UPDATE = "property_update"


class DeviceType(Enum):
    """Device type classification."""

    LIGHT = "light"
    OCCUPANCY_SENSOR = "occupancy_sensor"
    ILLUMINANCE_SENSOR = "illuminance_sensor"

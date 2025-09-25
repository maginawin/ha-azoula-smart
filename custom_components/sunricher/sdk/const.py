"""Constants for the Dali Center."""

# MQTT Topics
TOPIC_GATEWAY_PREFIX = "meribee/gateway"
TOPIC_PLATFORM_APP_PREFIX = "meribee/platform-app"
TOPIC_PLATFORM = "meribee/platform"
TOPIC_WEATHER_PREFIX = "meribee/weather/notify"

# Default values
DEFAULT_MQTT_PORT = 1883
DEFAULT_MQTT_QOS = 1

# Device types mapping (from protocol doc)
DEVICE_TYPE_MAPPING = {
    1: "switch",
    2: "light",
    3: "sensor",
    4: "cover",
    5: "climate",
    # Add more as needed
}

# Message methods (from protocol doc)
METHOD_DEVICE_ONLINE = "thing.device.online"
METHOD_DEVICE_OFFLINE = "thing.device.offline"
METHOD_PROPERTY_POST = "thing.device.propPost"
METHOD_EVENT_POST = "thing.device.eventPost"
METHOD_PROPERTY_SET = "thing.device.propSet"
METHOD_SERVICE_CALL = "thing.device.serviceCall"
METHOD_GET_ALL_DEVICES = "thing.subdev.getall"
METHOD_GET_ALL_DEVICES_REPLY = "thing.subdev.getall.reply"

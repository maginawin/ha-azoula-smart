"""Constants for the Dali Center."""

DOMAIN = "sunricher"

# MQTT Topics
TOPIC_GATEWAY_PREFIX = "meribee/gateway"
TOPIC_PLATFORM_APP_PREFIX = "meribee/platform-app"
TOPIC_PLATFORM = "meribee/platform"
TOPIC_WEATHER_PREFIX = "meribee/weather/notify"

# Default values
DEFAULT_MQTT_PORT = 1883

# Device types mapping (from protocol doc)
DEVICE_TYPE_MAPPING = {
    1: "switch",
    2: "light",
    3: "sensor",
    4: "cover",
    5: "climate",
    # Add more as needed
}

# Device type to Home Assistant platform mapping (from protocol doc Appendix)
DEVICE_TYPE_TO_PLATFORM = {
    # Lighting devices
    "0100": "light",  # ON/OFF Light
    "0101": "light",  # Dimmable Light
    "0102": "light",  # RGB Light
    "010c": "light",  # CCT Light
    "010d": "light",  # RGBCCT Light (Extended Colour Light)
    "0108": "light",  # On/Off Ballast
    "0109": "light",  # Dimmable Ballast
    "010a": "switch",  # On/Off Plug-in Unit
    "010b": "light",  # Dimmable Plug-in Unit
    # Sensor devices
    "0106": "sensor",  # Light Sensor
    "0107": "sensor",  # Occupancy Sensor
    "0302": "sensor",  # Temperature Sensor
    "0303": "sensor",  # Pump
    "0305": "sensor",  # Pressure Sensor
    "0306": "sensor",  # Flow sensor
    # Switch/Control devices
    "0000": "switch",  # ON/OFF Switch
    "0001": "switch",  # Level Control Switch
    "0004": "switch",  # Scene Selector
    "0006": "switch",  # Remote control
    "0051": "switch",  # Smart plug
}

# Device capabilities based on device type
DEVICE_CAPABILITIES = {
    "0100": {"on_off": True},  # ON/OFF Light
    "0101": {"on_off": True, "brightness": True},  # Dimmable Light
    "0102": {"on_off": True, "brightness": True, "rgb": True},  # RGB Light
    "010c": {"on_off": True, "brightness": True, "color_temp": True},  # CCT Light
    "010d": {
        "on_off": True,
        "brightness": True,
        "rgb": True,
        "color_temp": True,
    },  # RGBCCT Light
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

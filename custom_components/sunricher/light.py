"""Light platform for Azoula Smart integration."""

from __future__ import annotations

import json
import logging
from typing import Any
import uuid

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ColorMode,
    LightEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AzoulaSmartConfigEntry
from .const import (
    METHOD_DEVICE_OFFLINE,
    METHOD_DEVICE_ONLINE,
    METHOD_GET_ALL_DEVICES_REPLY,
    METHOD_PROPERTY_POST,
    TOPIC_GATEWAY_PREFIX,
)

_LOGGER = logging.getLogger(__name__)

# Device types that are lights
LIGHT_DEVICE_TYPES = ["0100", "0101", "0102"]  # ON/OFF, Dimmable, RGB


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AzoulaSmartConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up light entities from config entry."""
    api = entry.runtime_data

    # Store entities for dynamic addition/removal
    light_entities: dict[str, AzoulaSmartLight] = {}

    @callback
    def handle_device_message(topic: str, payload: dict[str, Any]) -> None:
        """Handle incoming device messages."""
        device_id = payload.get("deviceID")
        method = payload.get("method")

        _LOGGER.info(
            "Light platform received message: topic=%s, method=%s, deviceID=%s",
            topic,
            method,
            device_id,
        )

        if not device_id:
            _LOGGER.warning("Message missing deviceID: %s", payload)
            return

        if method == METHOD_DEVICE_ONLINE:
            # Check if it's a light device
            device_type = payload.get("deviceType")
            _LOGGER.info(
                "Device online: ID=%s, type=%s, all_payload=%s",
                device_id,
                device_type,
                payload,
            )

            if device_type in LIGHT_DEVICE_TYPES:
                if device_id not in light_entities:
                    # Create new light entity
                    light = AzoulaSmartLight(api, device_id, device_type, payload)
                    light_entities[device_id] = light
                    async_add_entities([light])
                    _LOGGER.info(
                        "Added light device: %s (type: %s)", device_id, device_type
                    )
                else:
                    _LOGGER.info("Light device %s already exists", device_id)
            else:
                _LOGGER.info(
                    "Device %s is not a light (type: %s)", device_id, device_type
                )

        elif method == METHOD_DEVICE_OFFLINE:
            _LOGGER.info("Device offline: %s", device_id)
            if device_id in light_entities:
                light_entities[device_id].set_available(False)

        elif method == METHOD_PROPERTY_POST:
            _LOGGER.debug(
                "Property update for device %s: %s",
                device_id,
                payload.get("params", {}),
            )
            if device_id in light_entities:
                light_entities[device_id].handle_property_update(
                    payload.get("params", {})
                )
            else:
                _LOGGER.debug(
                    "Received property update for unknown device: %s", device_id
                )

        elif method == METHOD_GET_ALL_DEVICES_REPLY:
            _LOGGER.info("Received device list response")
            data = payload.get("data", {})
            device_list = data.get("deviceList", [])
            _LOGGER.info("Found %d devices in gateway", len(device_list))

            for device in device_list:
                device_id = device.get("deviceID")
                device_type = device.get("deviceType")
                online = device.get("online", "0")

                _LOGGER.info(
                    "Device from list: ID=%s, type=%s, online=%s",
                    device_id,
                    device_type,
                    online,
                )

                if device_type in LIGHT_DEVICE_TYPES:
                    if device_id not in light_entities:
                        # Create new light entity
                        light = AzoulaSmartLight(api, device_id, device_type, device)
                        light_entities[device_id] = light
                        async_add_entities([light])
                        _LOGGER.info(
                            "Added light device from list: %s (type: %s)",
                            device_id,
                            device_type,
                        )

                        # Set availability based on online status
                        light.set_available(online == "1")
                    else:
                        # Update existing device availability
                        light_entities[device_id].set_available(online == "1")
                else:
                    _LOGGER.debug(
                        "Device %s is not a light (type: %s)", device_id, device_type
                    )

    # Register message handler
    api.add_message_callback(handle_device_message)


class AzoulaSmartLight(LightEntity):
    """Representation of an Azoula Smart light."""

    def __init__(
        self,
        api,
        device_id: str,
        device_type: str,
        device_info: dict[str, Any],
    ) -> None:
        """Initialize the light."""
        self._api = api
        self._device_id = device_id
        self._device_type = device_type

        # Extract device information
        self._name = device_info.get("deviceName", f"Light {device_id}")
        self._model = device_info.get("productId", "Unknown")

        # State tracking
        self._is_on = False
        self._brightness = 255
        self._color_temp = None
        self._available = True

        # Determine supported features based on device type
        self._supported_color_modes = {ColorMode.ONOFF}
        if device_type in ["0101", "0102"]:  # Dimmable or RGB
            self._supported_color_modes.add(ColorMode.BRIGHTNESS)
        if device_type == "0102":  # RGB light
            self._supported_color_modes.add(ColorMode.COLOR_TEMP)

    @property
    def unique_id(self) -> str:
        """Return unique ID for the entity."""
        return f"{self._api.gateway_id}_{self._device_id}"

    @property
    def name(self) -> str:
        """Return the name of the light."""
        return self._name

    @property
    def is_on(self) -> bool:
        """Return True if light is on."""
        return self._is_on

    @property
    def brightness(self) -> int | None:
        """Return the brightness of the light."""
        if ColorMode.BRIGHTNESS in self._supported_color_modes:
            return self._brightness
        return None

    @property
    def color_temp(self) -> int | None:
        """Return the color temperature."""
        return self._color_temp

    @property
    def supported_color_modes(self) -> set[ColorMode]:
        """Return the supported color modes."""
        return self._supported_color_modes

    @property
    def color_mode(self) -> ColorMode:
        """Return the current color mode."""
        if (
            self._color_temp is not None
            and ColorMode.COLOR_TEMP in self._supported_color_modes
        ):
            return ColorMode.COLOR_TEMP
        if ColorMode.BRIGHTNESS in self._supported_color_modes:
            return ColorMode.BRIGHTNESS
        return ColorMode.ONOFF

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available and self._api.is_connected

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information."""
        return {
            "identifiers": {("sunricher", self._device_id)},
            "name": self._name,
            "manufacturer": "Azoula Smart",
            "model": self._model,
            "via_device": ("sunricher", self._api.gateway_id),
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        params = {"OnOff": 1}

        # Handle brightness
        if (
            ATTR_BRIGHTNESS in kwargs
            and ColorMode.BRIGHTNESS in self._supported_color_modes
        ):
            brightness_percent = int((kwargs[ATTR_BRIGHTNESS] / 255) * 100)
            params["CurrentLevel"] = brightness_percent

        # Handle color temperature
        if (
            ATTR_COLOR_TEMP in kwargs
            and ColorMode.COLOR_TEMP in self._supported_color_modes
        ):
            # Convert from mireds to Kelvin and then to appropriate scale
            color_temp_k = int(1000000 / kwargs[ATTR_COLOR_TEMP])
            params["ColorTemperature"] = color_temp_k

        await self._send_command(params)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self._send_command({"OnOff": 0})

    async def _send_command(self, params: dict[str, Any]) -> None:
        """Send command to the device."""
        message = {
            "id": str(uuid.uuid4()),
            "version": "1.0",
            "deviceID": self._device_id,
            "params": params,
            "method": "thing.service.property.set",
        }

        topic = f"{TOPIC_GATEWAY_PREFIX}/{self._api.gateway_id}"
        await self._api.async_publish(topic, json.dumps(message))

        _LOGGER.debug("Sent command to %s: %s", self._device_id, params)

    @callback
    def handle_property_update(self, params: dict[str, Any]) -> None:
        """Handle property updates from the device."""
        updated = False

        if "OnOff" in params:
            new_state = bool(int(params["OnOff"]))
            if new_state != self._is_on:
                self._is_on = new_state
                updated = True

        if (
            "CurrentLevel" in params
            and ColorMode.BRIGHTNESS in self._supported_color_modes
        ):
            # Convert from percentage to 0-255 range
            brightness_percent = int(params["CurrentLevel"])
            new_brightness = int((brightness_percent / 100) * 255)
            if new_brightness != self._brightness:
                self._brightness = new_brightness
                updated = True

        if (
            "ColorTemperature" in params
            and ColorMode.COLOR_TEMP in self._supported_color_modes
        ):
            # Convert Kelvin to mireds
            color_temp_k = int(params["ColorTemperature"])
            new_color_temp = int(1000000 / color_temp_k) if color_temp_k > 0 else None
            if new_color_temp != self._color_temp:
                self._color_temp = new_color_temp
                updated = True

        if updated:
            self.async_write_ha_state()

    @callback
    def set_available(self, available: bool) -> None:
        """Set the availability of the entity."""
        if self._available != available:
            self._available = available
            self.async_write_ha_state()

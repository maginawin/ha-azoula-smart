"""API client for Azoula Smart gateway."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import json
import logging
from typing import Any

import paho.mqtt.client as mqtt_client

from homeassistant.core import HomeAssistant

from .const import (
    DEFAULT_MQTT_PORT,
    DEFAULT_MQTT_QOS,
    METHOD_DEVICE_OFFLINE,
    METHOD_DEVICE_ONLINE,
    METHOD_EVENT_POST,
    METHOD_GET_ALL_DEVICES_REPLY,
    METHOD_PROPERTY_POST,
    TOPIC_GATEWAY_PREFIX,
    TOPIC_PLATFORM_APP_PREFIX,
)

_LOGGER = logging.getLogger(__name__)


class AzoulaSmartAPI:
    """API client for Azoula Smart gateway."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        username: str,
        password: str,
        gateway_id: str | None = None,
    ) -> None:
        """Initialize the API client."""
        self.hass = hass
        self.host = host
        self.username = username
        self.password = password
        self.gateway_id = gateway_id or "unknown"

        self._client: mqtt_client.Client | None = None
        self._connected = False
        self._subscriptions: dict[str, list[Callable[[str, Any], None]]] = {}
        self._message_callbacks: list[Callable[[str, dict[str, Any]], None]] = []

    async def async_connect(self) -> bool:
        """Connect to the MQTT broker."""
        if self._client is not None:
            return self._connected

        try:
            self._client = mqtt_client.Client()
            self._client.username_pw_set(self.username, self.password)

            # Set up callbacks
            self._client.on_connect = self._on_connect
            self._client.on_disconnect = self._on_disconnect
            self._client.on_message = self._on_message

            # Connect to broker
            await self.hass.async_add_executor_job(
                self._client.connect, self.host, DEFAULT_MQTT_PORT, 60
            )

            # Start the loop
            self._client.loop_start()

            # Wait for connection
            for _ in range(50):  # 5 second timeout
                if self._connected:
                    break
                await asyncio.sleep(0.1)

            if self._connected:
                # Subscribe to platform-app topic for this gateway
                topic = f"{TOPIC_PLATFORM_APP_PREFIX}/{self.gateway_id}"
                await self.async_subscribe(topic)

                # Also subscribe to a wildcard topic to catch all messages for debugging
                debug_topic = f"{TOPIC_PLATFORM_APP_PREFIX}/+"
                await self.async_subscribe(debug_topic)

                _LOGGER.info("Connected to Azoula Smart gateway at %s", self.host)
                _LOGGER.info("Subscribed to MQTT topic: %s", topic)
                _LOGGER.info("Subscribed to debug topic: %s", debug_topic)
                _LOGGER.info("Gateway ID: %s", self.gateway_id)

                # Request all devices after successful connection
                await self.async_get_all_devices()
                return True

            _LOGGER.error("Failed to connect to MQTT broker at %s", self.host)
            return False

        except (OSError, ValueError) as e:
            _LOGGER.error("Error connecting to MQTT broker: %s", e)
            return False

    async def async_disconnect(self) -> None:
        """Disconnect from the MQTT broker."""
        if self._client is not None:
            self._client.loop_stop()
            await self.hass.async_add_executor_job(self._client.disconnect)
            self._client = None
            self._connected = False

    async def async_subscribe(self, topic: str) -> None:
        """Subscribe to a MQTT topic."""
        if self._client is not None and self._connected:
            await self.hass.async_add_executor_job(
                self._client.subscribe, topic, DEFAULT_MQTT_QOS
            )
            _LOGGER.debug("Subscribed to topic: %s", topic)

    async def async_publish(self, topic: str, payload: str) -> None:
        """Publish a message to a MQTT topic."""
        if self._client is not None and self._connected:
            await self.hass.async_add_executor_job(
                self._client.publish, topic, payload, DEFAULT_MQTT_QOS
            )
            _LOGGER.debug("Published to topic %s: %s", topic, payload)

    async def async_get_all_devices(self) -> None:
        """Request all devices from the gateway."""
        import uuid

        message = {
            "id": str(uuid.uuid4()),
            "deviceID": self.gateway_id,
            "method": "thing.subdev.getall",
        }

        topic = f"{TOPIC_GATEWAY_PREFIX}/{self.gateway_id}"
        await self.async_publish(topic, json.dumps(message))
        _LOGGER.info("Requested all devices from gateway: %s", self.gateway_id)

    def add_message_callback(
        self, callback: Callable[[str, dict[str, Any]], None]
    ) -> None:
        """Add a message callback."""
        self._message_callbacks.append(callback)
        _LOGGER.info(
            "Registered message callback: %s, total callbacks: %d",
            callback.__name__ if hasattr(callback, "__name__") else str(callback),
            len(self._message_callbacks),
        )

    def remove_message_callback(
        self, callback: Callable[[str, dict[str, Any]], None]
    ) -> None:
        """Remove a message callback."""
        if callback in self._message_callbacks:
            self._message_callbacks.remove(callback)

    def _on_connect(self, _client: Any, _userdata: Any, _flags: Any, rc: int) -> None:
        """Handle MQTT connection."""
        if rc == 0:
            self._connected = True
            _LOGGER.debug("MQTT connected with result code %s", rc)
        else:
            self._connected = False
            _LOGGER.error("MQTT connection failed with result code %s", rc)

    def _on_disconnect(self, _client: Any, _userdata: Any, rc: int) -> None:
        """Handle MQTT disconnection."""
        self._connected = False
        _LOGGER.debug("MQTT disconnected with result code %s", rc)

    def _on_message(self, client: Any, userdata: Any, msg: Any) -> None:
        """Handle incoming MQTT messages."""
        try:
            topic = msg.topic
            payload_str = msg.payload.decode("utf-8")

            _LOGGER.info("=== MQTT MESSAGE RECEIVED ===")
            _LOGGER.info("Topic: %s", topic)
            _LOGGER.info("Raw payload: %s", payload_str)

            # Try to parse JSON payload
            try:
                payload = json.loads(payload_str)
                _LOGGER.info("Successfully parsed JSON: %s", payload)
            except json.JSONDecodeError as e:
                _LOGGER.warning(
                    "Failed to parse JSON message: %s, Error: %s", payload_str, e
                )
                return

            # Process the message based on method
            method = payload.get("method")
            device_id = payload.get("deviceID")
            _LOGGER.info(
                "Message details - method: %s, deviceID: %s", method, device_id
            )

            # Log all supported methods for comparison
            supported_methods = [
                METHOD_DEVICE_ONLINE,
                METHOD_DEVICE_OFFLINE,
                METHOD_PROPERTY_POST,
                METHOD_EVENT_POST,
                METHOD_GET_ALL_DEVICES_REPLY,
            ]
            _LOGGER.info("Supported methods: %s", supported_methods)

            if method in supported_methods:
                _LOGGER.info("✅ Processing message with supported method: %s", method)
                # Schedule callback execution in the event loop
                self.hass.loop.call_soon_threadsafe(
                    self._handle_message, topic, payload
                )
            else:
                _LOGGER.info("❌ Ignoring message with unsupported method: %s", method)

        except (ValueError, UnicodeDecodeError) as e:
            _LOGGER.error("Error processing MQTT message: %s", e)

    def _handle_message(self, topic: str, payload: dict[str, Any]) -> None:
        """Handle processed message in the event loop."""
        _LOGGER.info(
            "Executing message callbacks, count: %d", len(self._message_callbacks)
        )
        for i, callback in enumerate(self._message_callbacks):
            try:
                _LOGGER.info(
                    "Calling callback %d: %s",
                    i,
                    callback.__name__
                    if hasattr(callback, "__name__")
                    else str(callback),
                )
                callback(topic, payload)
            except Exception as e:  # Callback exceptions are unknown, so keep broad
                _LOGGER.error("Error in message callback %d: %s", i, e)

    @property
    def is_connected(self) -> bool:
        """Return True if connected to MQTT broker."""
        return self._connected

"""API client for Azoula Smart gateway."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import json
import logging
import time
from typing import Any
import uuid

import paho.mqtt.client as paho_mqtt

# Backward compatibility with paho-mqtt < 2.0.0
try:
    from paho.mqtt.enums import CallbackAPIVersion

    HAS_CALLBACK_API_VERSION = True
except ImportError:
    # paho-mqtt < 2.0.0 doesn't have CallbackAPIVersion
    HAS_CALLBACK_API_VERSION = False  # pyright: ignore[reportConstantRedefinition]

from .const import (
    DEFAULT_MQTT_PORT,
    METHOD_DEVICE_OFFLINE,
    METHOD_DEVICE_ONLINE,
    METHOD_GET_ALL_DEVICES,
    METHOD_GET_ALL_DEVICES_REPLY,
    METHOD_PROPERTY_POST,
    TOPIC_GATEWAY_PREFIX,
    TOPIC_PLATFORM_APP_PREFIX,
)
from .exceptions import AzoulaSmartHubError
from .types import DeviceType

_LOGGER = logging.getLogger(__name__)


class AzoulaSmartHub:
    """API client for Azoula Smart gateway."""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        gateway_id: str,
    ) -> None:
        """Initialize the API client."""

        # Gateway information
        self._host = host
        self._port = DEFAULT_MQTT_PORT
        self._username = username
        self._password = password
        self._gateway_id = gateway_id

        # MQTT topics
        self._sub_topic = f"{TOPIC_PLATFORM_APP_PREFIX}/{self._gateway_id}"
        self._pub_topic = f"{TOPIC_GATEWAY_PREFIX}/{self._gateway_id}"

        # MQTT client - handle compatibility between paho-mqtt versions
        # Add timestamp to client ID to avoid conflicts
        timestamp = int(time.time())
        client_id = f"ha_dali_center_{self._gateway_id}_{timestamp}"

        if HAS_CALLBACK_API_VERSION:
            # paho-mqtt >= 2.0.0
            self._mqtt_client = paho_mqtt.Client(
                CallbackAPIVersion.VERSION2,  # pyright: ignore[reportPossiblyUnboundVariable]
                client_id=client_id,
                protocol=paho_mqtt.MQTTv311,
            )
        else:
            # paho-mqtt < 2.0.0
            self._mqtt_client = paho_mqtt.Client(
                client_id=client_id,
                protocol=paho_mqtt.MQTTv311,
            )

        self._mqtt_client.enable_logger()

        # Connection result
        self._connect_result: int | None = None
        self._connection_event = asyncio.Event()

        # Set up client callbacks
        self._mqtt_client.on_connect = self._on_connect
        self._mqtt_client.on_disconnect = self._on_disconnect
        self._mqtt_client.on_message = self._on_message

        # Event callbacks - following pySrDaliGateway pattern
        self._on_online_status: Callable[[str, bool], None] | None = None
        self._on_device_status: Callable[[str, dict[str, Any]], None] | None = None
        self._on_property_update: Callable[[str, dict[str, Any]], None] | None = None

        # Device discovery state
        self._devices_received = asyncio.Event()
        self._devices_result: list[DeviceType] = []

    @property
    def on_device_status(self) -> Callable[[str, dict[str, Any]], None] | None:
        """Get device status change callback."""
        return self._on_device_status

    @on_device_status.setter
    def on_device_status(
        self, callback: Callable[[str, dict[str, Any]], None] | None
    ) -> None:
        """Set device status change callback."""
        self._on_device_status = callback

    @property
    def on_property_update(self) -> Callable[[str, dict[str, Any]], None] | None:
        """Get device property update callback."""
        return self._on_property_update

    @on_property_update.setter
    def on_property_update(
        self, callback: Callable[[str, dict[str, Any]], None] | None
    ) -> None:
        """Set device property update callback."""
        self._on_property_update = callback

    def _on_connect(
        self,
        client: paho_mqtt.Client,
        userdata: Any,
        flags: Any,
        rc: int,
        properties: Any = None,
    ) -> None:
        self._connect_result = rc
        self._connection_event.set()

        if rc == 0:
            _LOGGER.debug(
                "Gateway %s: MQTT connection established to %s:%s",
                self._gateway_id,
                self._host,
                self._port,
            )
            self._mqtt_client.subscribe(self._sub_topic)
            _LOGGER.debug(
                "Gateway %s: Subscribed to MQTT topic %s",
                self._gateway_id,
                self._sub_topic,
            )

            # Trigger online_status callback with gateway SN as device ID and True status
            if self._on_online_status:
                self._on_online_status(self._gateway_id, True)
        else:
            _LOGGER.error(
                "Gateway %s: MQTT connection failed with code %s", self._gateway_id, rc
            )

    def _on_disconnect(
        self,
        client: paho_mqtt.Client,
        userdata: Any,
        *args: Any,
    ) -> None:
        # Handle different paho-mqtt versions:
        # v1.6.x: (client, userdata, rc)
        # v2.0.0+: (client, userdata, disconnect_flags, reason_code, properties)
        if HAS_CALLBACK_API_VERSION and len(args) >= 2:
            # paho-mqtt >= 2.0.0
            reason_code = args[1]  # disconnect_flags, reason_code, properties
        elif len(args) >= 1:
            # paho-mqtt < 2.0.0
            reason_code = args[0]  # rc
        else:
            reason_code = 0

        if reason_code != 0:
            _LOGGER.warning(
                "Gateway %s: Unexpected MQTT disconnection (%s:%s) - Reason code: %s",
                self._gateway_id,
                self._host,
                self._port,
                reason_code,
            )
        else:
            _LOGGER.debug("Gateway %s: MQTT disconnection completed", self._gateway_id)

        # Trigger online_status callback with gateway SN as device ID and False status
        if self._on_online_status:
            self._on_online_status(self._gateway_id, False)

    def _on_message(
        self, client: paho_mqtt.Client, userdata: Any, msg: paho_mqtt.MQTTMessage
    ) -> None:
        try:
            payload_json = json.loads(msg.payload.decode("utf-8", errors="replace"))
            _LOGGER.debug(
                "Gateway %s: Received MQTT message on topic %s: %s",
                self._gateway_id,
                msg.topic,
                payload_json,
            )

            method = payload_json.get("method")
            if not method:
                _LOGGER.warning(
                    "Gateway %s: Received MQTT message without method field",
                    self._gateway_id,
                )
                return

            command_handlers: dict[str, Callable[[dict[str, Any]], None]] = {
                METHOD_GET_ALL_DEVICES_REPLY: self._handle_devices_response,
                METHOD_DEVICE_ONLINE: self._handle_device_online,
                METHOD_DEVICE_OFFLINE: self._handle_device_offline,
                METHOD_PROPERTY_POST: self._handle_property_post,
            }

            handler = command_handlers.get(method)
            if handler:
                handler(payload_json)
            else:
                _LOGGER.debug(
                    "Gateway %s: Unhandled MQTT command '%s', payload: %s",
                    self._gateway_id,
                    method,
                    payload_json,
                )

        except json.JSONDecodeError:
            _LOGGER.exception(
                "Gateway %s: Failed to decode MQTT message payload: %s",
                self._gateway_id,
                msg.payload,
            )
        except (ValueError, KeyError, TypeError):
            _LOGGER.exception(
                "Gateway %s: Error processing MQTT message", self._gateway_id
            )

    def _handle_devices_response(self, payload: dict[str, Any]) -> None:
        """Handle device list response."""

        code = payload.get("code", 0)

        if code != 200:
            _LOGGER.error(
                "Gateway %s: Device list request failed with code %s",
                self._gateway_id,
                code,
            )
            self._devices_received.set()
            return

        data = payload.get("data", {})
        device_list = data.get("deviceList", [])

        _LOGGER.debug(
            "Gateway %s: Received device list with %d devices",
            self._gateway_id,
            len(device_list),
        )

        for raw_device_data in device_list:
            device = DeviceType(
                device_id=raw_device_data.get("deviceID", ""),
                profile=raw_device_data.get("profile", ""),
                device_type=raw_device_data.get("deviceType", ""),
                product_id=raw_device_data.get("productId", ""),
                version=raw_device_data.get("version", ""),
                device_status=raw_device_data.get("deviceStatus", ""),
                online=raw_device_data.get("online", ""),
                protocol=raw_device_data.get("protocol", ""),
                manufacturer=raw_device_data.get("manufacturer", ""),
                manufacturer_code=raw_device_data.get("manufacturerCode", 0),
                image_type=raw_device_data.get("imageType", 0),
                household_id=raw_device_data.get("householdId", ""),
                is_added=raw_device_data.get("isAdded", ""),
            )
            if device not in self._devices_result:
                self._devices_result.append(device)

        self._devices_received.set()

    def _handle_device_online(self, payload: dict[str, Any]) -> None:
        """Handle device online notification."""
        device_id = payload.get("deviceID", "")

        _LOGGER.debug(
            "Gateway %s: Device %s came online",
            self._gateway_id,
            device_id,
        )

        # Trigger device status callback
        if self._on_device_status:
            self._on_device_status(device_id, {"online": True})

    def _handle_device_offline(self, payload: dict[str, Any]) -> None:
        """Handle device offline notification."""
        device_id = payload.get("deviceID", "")

        _LOGGER.debug(
            "Gateway %s: Device %s went offline",
            self._gateway_id,
            device_id,
        )

        # Trigger device status callback
        if self._on_device_status:
            self._on_device_status(device_id, {"online": False})

    def _handle_property_post(self, payload: dict[str, Any]) -> None:
        """Handle device property update."""
        device_id = payload.get("deviceID", "")
        params = payload.get("params", {})

        _LOGGER.debug(
            "Gateway %s: Device %s property update: %s",
            self._gateway_id,
            device_id,
            params,
        )

        # Trigger property update callback
        if self._on_property_update:
            self._on_property_update(device_id, params)

    async def connect(self) -> None:
        """Connect to the MQTT broker."""
        self._connection_event.clear()
        self._connect_result = 0
        self._mqtt_client.username_pw_set(self._username, self._password)

        try:
            _LOGGER.info(
                "Attempting connection to gateway %s at %s:%s",
                self._gateway_id,
                self._host,
                self._port,
            )
            self._mqtt_client.connect(self._host, self._port)
            self._mqtt_client.loop_start()
            await asyncio.wait_for(self._connection_event.wait(), timeout=10)

            if self._connect_result == 0:
                _LOGGER.info(
                    "Successfully connected to gateway %s at %s:%s",
                    self._gateway_id,
                    self._host,
                    self._port,
                )
                return

        except TimeoutError as err:
            _LOGGER.exception(
                "Connection timeout to gateway %s at %s:%s after 10 seconds - check network connectivity",
                self._gateway_id,
                self._host,
                self._port,
            )
            raise AzoulaSmartHubError(
                f"Connection timeout to gateway {self._gateway_id}", self._gateway_id
            ) from err
        except (ConnectionRefusedError, OSError) as err:
            _LOGGER.exception(
                "Network error connecting to gateway %s at %s:%s - check if gateway is powered on and accessible",
                self._gateway_id,
                self._host,
                self._port,
            )
            raise AzoulaSmartHubError(
                f"Network error connecting to gateway {self._gateway_id}: {err}",
                self._gateway_id,
            ) from err

        if self._connect_result in (4, 5):
            _LOGGER.exception(
                "Authentication failed for gateway %s (code %s) with credentials user='%s'. "
                "Please press the gateway button and retry",
                self._gateway_id,
                self._connect_result,
                self._username,
            )
            raise AzoulaSmartHubError(
                f"Authentication failed for gateway {self._gateway_id}. "
                "Please press the gateway button and retry",
                self._gateway_id,
            )
        _LOGGER.error(
            "Connection failed for gateway %s with result code %s",
            self._gateway_id,
            self._connect_result,
        )
        raise AzoulaSmartHubError(
            f"Connection failed for gateway {self._gateway_id} "
            f"with code {self._connect_result}"
        )

    async def disconnect(self) -> None:
        """Disconnect from the MQTT broker."""
        try:
            self._mqtt_client.loop_stop()
            self._mqtt_client.disconnect()
            self._connection_event.clear()
            _LOGGER.info("Successfully disconnected from gateway %s", self._gateway_id)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            _LOGGER.exception(
                "Error during disconnect from gateway %s", self._gateway_id
            )
            raise AzoulaSmartHubError(
                f"Failed to disconnect from gateway {self._gateway_id}: {exc}"
            ) from exc

    async def get_all_devices(self) -> list[DeviceType]:
        """Get all devices from the gateway."""
        self._devices_received = asyncio.Event()
        self._devices_result.clear()

        message_id = str(uuid.uuid4()).upper()
        request_payload = {
            "id": message_id,
            "deviceID": self._gateway_id,
            "method": METHOD_GET_ALL_DEVICES,
        }

        _LOGGER.debug(
            "Gateway %s: Sending device discovery request with message ID %s",
            self._gateway_id,
            message_id,
        )

        self._mqtt_client.publish(self._pub_topic, json.dumps(request_payload))

        try:
            await asyncio.wait_for(self._devices_received.wait(), timeout=30.0)
        except TimeoutError:
            _LOGGER.warning(
                "Gateway %s: Timeout waiting for device discovery response",
                self._gateway_id,
            )

        _LOGGER.info(
            "Gateway %s: Device discovery completed, found %d device(s)",
            self._gateway_id,
            len(self._devices_result),
        )
        return self._devices_result

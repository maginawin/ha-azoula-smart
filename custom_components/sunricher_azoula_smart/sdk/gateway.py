"""API client for Azoula Smart gateway."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import json
import logging
from typing import Any
import uuid

import paho.mqtt.client as paho_mqtt

try:
    from paho.mqtt.enums import CallbackAPIVersion

    HAS_CALLBACK_API_VERSION = True
except ImportError:
    # paho-mqtt < 2.0.0 doesn't have CallbackAPIVersion
    HAS_CALLBACK_API_VERSION = False  # pyright: ignore[reportConstantRedefinition]

from .const import (
    DEFAULT_DISCOVERY_TIMEOUT,
    DEFAULT_MQTT_PORT,
    DEFAULT_TSL_TIMEOUT,
    METHOD_DEVICE_DISCOVER,
    METHOD_DEVICE_DISCOVER_REPLY,
    METHOD_PROPERTY_GET,
    METHOD_PROPERTY_GET_REPLY,
    METHOD_PROPERTY_POST,
    METHOD_SERVICE_INVOKE,
    METHOD_SERVICE_INVOKE_REPLY,
    METHOD_TSL_GET,
    METHOD_TSL_GET_REPLY,
    SERVICE_PROPERTY_GET,
    TOPIC_GATEWAY_PREFIX,
    TOPIC_PLATFORM_APP_PREFIX,
    TSL_LANGUAGE_ENGLISH,
    CallbackEventType,
)
from .device import AzoulaDevice
from .exceptions import AzoulaGatewayError
from .types import DeviceTSL, ListenerCallback, PropertyParams

_LOGGER = logging.getLogger(__name__)


class AzoulaGateway:
    """API client for Azoula Smart gateway."""

    def __init__(
        self, host: str, username: str, password: str, gateway_id: str
    ) -> None:
        """Initialize the API client."""
        self.gateway_id = gateway_id
        self._host = host
        self._port = DEFAULT_MQTT_PORT
        self._username = username
        self._password = password

        self._sub_topic = f"{TOPIC_PLATFORM_APP_PREFIX}/{self.gateway_id}"
        self._pub_topic = f"{TOPIC_GATEWAY_PREFIX}/{self.gateway_id}"

        # Generate unique client_id to avoid conflicts
        client_id = f"ha_azoula_{self.gateway_id}_{uuid.uuid4().hex[:8]}"

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

        self._connect_result: int | None = None
        self._connection_event = asyncio.Event()

        self._mqtt_client.on_connect = self._on_connect
        self._mqtt_client.on_disconnect = self._on_disconnect
        self._mqtt_client.on_message = self._on_message

        # Multi-listener support
        self._listeners: dict[CallbackEventType, list[Callable[..., None]]] = {
            CallbackEventType.ONLINE_STATUS: [],
            CallbackEventType.PROPERTY_UPDATE: [],
        }
        self._background_tasks: set[asyncio.Task[None]] = set()

        # Device discovery state
        self._discovered_devices: list[AzoulaDevice] = []
        self._devices_received: asyncio.Event | None = None
        self._expected_page_count: int = 0
        self._current_page: int = 0

        # TSL (Thing Specification Language) state
        self._tsl_pending_requests: dict[str, asyncio.Event] = {}
        self._tsl_responses: dict[str, DeviceTSL | None] = {}

    def register_listener(
        self,
        event_type: CallbackEventType,
        listener: ListenerCallback,
    ) -> Callable[[], None]:
        """Register a listener for a specific event type."""
        if event_type not in self._listeners:
            return lambda: None

        self._listeners[event_type].append(listener)

        return lambda: self._listeners[event_type].remove(listener)

    def _notify_listeners(
        self,
        event_type: CallbackEventType,
        dev_id: str,
        data: bool | PropertyParams,
    ) -> None:
        """Notify all registered listeners for a specific event type."""
        for listener in self._listeners.get(event_type, []):
            if asyncio.iscoroutinefunction(listener):
                task = asyncio.create_task(listener(dev_id, data))
                self._background_tasks.add(task)
                task.add_done_callback(self._background_tasks.discard)
            else:
                listener(dev_id, data)

    async def connect(self) -> None:
        """Connect to the MQTT broker."""
        self._connection_event.clear()
        self._connect_result = 0
        self._mqtt_client.username_pw_set(self._username, self._password)

        try:
            self._mqtt_client.connect(self._host, self._port)
            self._mqtt_client.loop_start()
            await asyncio.wait_for(self._connection_event.wait(), timeout=10)
        except TimeoutError as err:
            raise AzoulaGatewayError("Connection timeout", self.gateway_id) from err
        except (ConnectionRefusedError, OSError) as err:
            raise AzoulaGatewayError(f"Network error: {err}", self.gateway_id) from err

        if self._connect_result == 0:
            _LOGGER.info(
                "Connected to gateway %s at %s:%s",
                self.gateway_id,
                self._host,
                self._port,
            )
            return

        if self._connect_result in (4, 5):
            raise AzoulaGatewayError(
                "Authentication failed. Please press the gateway button and retry",
                self.gateway_id,
            )

        raise AzoulaGatewayError(
            f"Connection failed with code {self._connect_result}",
            self.gateway_id,
        )

    async def disconnect(self) -> None:
        """Disconnect from the MQTT broker."""
        self._mqtt_client.loop_stop()
        self._mqtt_client.disconnect()
        self._connection_event.clear()

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
            self._mqtt_client.subscribe(self._sub_topic)
            _LOGGER.debug(
                "Subscribed to topic %s for gateway %s",
                self._sub_topic,
                self.gateway_id,
            )

            self._notify_listeners(
                CallbackEventType.ONLINE_STATUS, self.gateway_id, True
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
            reason_code = args[1]
        elif len(args) >= 1:
            reason_code = args[0]
        else:
            reason_code = 0

        if reason_code != 0:
            _LOGGER.warning(
                "Unexpected MQTT disconnection for gateway %s (code %s)",
                self.gateway_id,
                reason_code,
            )
        else:
            _LOGGER.debug("MQTT disconnected for gateway %s", self.gateway_id)

        self._notify_listeners(CallbackEventType.ONLINE_STATUS, self.gateway_id, False)

    def _on_message(
        self, client: paho_mqtt.Client, userdata: Any, msg: paho_mqtt.MQTTMessage
    ) -> None:
        try:
            payload_json = json.loads(msg.payload.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            _LOGGER.warning(
                "Invalid JSON in MQTT message from gateway %s: %s",
                self.gateway_id,
                msg.payload,
            )
            return

        _LOGGER.debug(
            "Received MQTT message from gateway %s on topic %s: %s",
            self.gateway_id,
            msg.topic,
            payload_json,
        )

        method = payload_json.get("method")
        if not method:
            _LOGGER.debug(
                "Received MQTT message without method field from gateway %s",
                self.gateway_id,
            )
            return

        method_handlers: dict[str, Callable[[dict[str, Any]], None]] = {
            METHOD_DEVICE_DISCOVER_REPLY: self._handle_device_discover_response,
            METHOD_PROPERTY_POST: self._handle_property_post,
            METHOD_PROPERTY_GET_REPLY: self._handle_property_get_reply,
            METHOD_SERVICE_INVOKE_REPLY: self._handle_service_reply,
            METHOD_TSL_GET_REPLY: self._handle_tsl_reply,
        }

        handler = method_handlers.get(method)
        if handler:
            handler(payload_json)
        else:
            _LOGGER.debug(
                "Unhandled method %s from gateway %s", method, self.gateway_id
            )

    async def discover_devices(
        self,
        load_tsl: bool = True,
    ) -> list[AzoulaDevice]:
        """Discover all sub-devices under the gateway.

        Args:
            load_tsl: If True, automatically load TSL for each discovered device

        Returns:
            List of discovered AzoulaDevice instances
        """
        self._devices_received = asyncio.Event()
        self._discovered_devices = []
        self._expected_page_count = 0
        self._current_page = 0

        request_payload = {
            "id": str(uuid.uuid4()),
            "deviceID": self.gateway_id,
            "method": METHOD_DEVICE_DISCOVER,
        }

        self._mqtt_client.publish(
            self._pub_topic,
            json.dumps(request_payload),
        )

        try:
            await asyncio.wait_for(
                self._devices_received.wait(),
                timeout=DEFAULT_DISCOVERY_TIMEOUT,
            )
        except TimeoutError:
            _LOGGER.warning(
                "Device discovery timeout for gateway %s",
                self.gateway_id,
            )

        # Load TSL for each discovered device if requested
        if load_tsl:
            for device in self._discovered_devices:
                _LOGGER.debug(
                    "Loading TSL for device %s (%s)",
                    device.device_id,
                    device.name,
                )
                tsl = await self.get_device_tsl(device.device_id)
                device.tsl = tsl

        return self._discovered_devices.copy()

    async def invoke_service(
        self,
        device_id: str,
        service_identifier: str,
        params: dict[str, Any] | list[str] | None = None,
    ) -> None:
        """Invoke a device service (thing.service)."""
        request_payload: dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "deviceID": device_id,
            "method": METHOD_SERVICE_INVOKE,
            "identifier": service_identifier,
            "params": params if params is not None else {},
        }

        self._mqtt_client.publish(
            self._pub_topic,
            json.dumps(request_payload),
        )

        _LOGGER.debug(
            "Invoked service %s for device %s with params %s on gateway %s",
            service_identifier,
            device_id,
            params,
            self.gateway_id,
        )

    async def get_device_properties(
        self,
        device_id: str,
        properties: list[str],
    ) -> None:
        """Request device properties via thing.service.property.get.

        The device will respond with property.post event containing the values.
        """
        request_payload: dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "deviceID": device_id,
            "method": METHOD_PROPERTY_GET,
            "identifier": SERVICE_PROPERTY_GET,
            "params": properties,
        }

        self._mqtt_client.publish(
            self._pub_topic,
            json.dumps(request_payload),
        )

        _LOGGER.debug(
            "Requested properties %s for device %s on gateway %s",
            properties,
            device_id,
            self.gateway_id,
        )

    async def get_device_tsl(
        self,
        device_id: str,
        language: str = TSL_LANGUAGE_ENGLISH,
        timeout: float = DEFAULT_TSL_TIMEOUT,
    ) -> DeviceTSL | None:
        """Get device Thing Specification Language (物模型) for a device.

        Args:
            device_id: Device ID to get TSL for
            language: TSL language (english or chinese), defaults to english
            timeout: Request timeout in seconds

        Returns:
            DeviceTSL object if successful, None if request fails or times out
        """
        request_id = str(uuid.uuid4())
        request_payload: dict[str, Any] = {
            "id": request_id,
            "version": "1.0",
            "deviceID": device_id,
            "language": language,
            "method": METHOD_TSL_GET,
        }

        # Create event for this request
        event = asyncio.Event()
        self._tsl_pending_requests[request_id] = event
        self._tsl_responses[request_id] = None

        try:
            self._mqtt_client.publish(
                self._pub_topic,
                json.dumps(request_payload),
            )

            _LOGGER.debug(
                "Requested TSL for device %s (language: %s) on gateway %s",
                device_id,
                language,
                self.gateway_id,
            )

            await asyncio.wait_for(event.wait(), timeout=timeout)
            return self._tsl_responses.get(request_id)

        except TimeoutError:
            _LOGGER.warning(
                "TSL request timeout for device %s on gateway %s",
                device_id,
                self.gateway_id,
            )
            return None
        finally:
            # Cleanup
            self._tsl_pending_requests.pop(request_id, None)
            self._tsl_responses.pop(request_id, None)

    def _handle_device_discover_response(self, payload: dict[str, Any]) -> None:
        """Handle device discovery response with pagination support."""
        if payload.get("code") != 200:
            if self._devices_received:
                self._devices_received.set()
            return

        page_count = payload.get("PageCount", 1)
        current_page = payload.get("CurrentPage", 1)

        if self._expected_page_count == 0:
            self._expected_page_count = page_count

        data = payload.get("data", {})
        device_list = data.get("deviceList", [])

        for device_data in device_list:
            device = AzoulaDevice.from_dict(device_data)
            # Avoid duplicates
            if not any(
                d.unique_id == device.unique_id for d in self._discovered_devices
            ):
                self._discovered_devices.append(device)

        self._current_page = current_page

        if current_page >= page_count:
            if self._devices_received:
                self._devices_received.set()

    def _handle_property_post(self, payload: dict[str, Any]) -> None:
        """Handle property post message (thing.event.property.post)."""
        device_id = payload.get("deviceID")
        params = payload.get("params", {})

        if not device_id:
            return

        _LOGGER.debug(
            "Property update for device %s on gateway %s: %s",
            device_id,
            self.gateway_id,
            params,
        )

        # Notify listeners about property update
        self._notify_listeners(
            CallbackEventType.PROPERTY_UPDATE,
            device_id,
            params,
        )

    def _handle_property_get_reply(self, payload: dict[str, Any]) -> None:
        """Handle property get reply (thing.service.property.get.reply)."""
        code = payload.get("code", 0)
        device_id = payload.get("deviceID")
        data = payload.get("data", {})

        if code != 200:
            _LOGGER.warning(
                "Property get failed for device %s on gateway %s: code=%s",
                device_id,
                self.gateway_id,
                code,
            )
            return

        if not device_id or not data:
            return

        _LOGGER.debug(
            "Property get reply for device %s on gateway %s: %s",
            device_id,
            self.gateway_id,
            data,
        )

        normalized_data = {}
        for prop_name, prop_value in data.items():
            normalized_data[prop_name] = {"value": prop_value}

        self._notify_listeners(
            CallbackEventType.PROPERTY_UPDATE,
            device_id,
            normalized_data,  # type: ignore[arg-type]
        )

    def _handle_service_reply(self, payload: dict[str, Any]) -> None:
        """Handle service invocation reply (thing.service.reply)."""
        code = payload.get("code", 0)
        request_id = payload.get("id")

        if code != 200:
            _LOGGER.warning(
                "Service invocation failed on gateway %s: code=%s, id=%s",
                self.gateway_id,
                code,
                request_id,
            )

    def _handle_tsl_reply(self, payload: dict[str, Any]) -> None:
        """Handle TSL get reply (thing.tsl.reply)."""
        code = payload.get("code", 0)
        request_id = payload.get("id")
        message = payload.get("message", "")

        if not request_id or request_id not in self._tsl_pending_requests:
            _LOGGER.debug(
                "Received TSL reply for unknown request %s on gateway %s",
                request_id,
                self.gateway_id,
            )
            return

        if code != 200:
            _LOGGER.warning(
                "TSL request failed on gateway %s: code=%s, message=%s, id=%s",
                self.gateway_id,
                code,
                message,
                request_id,
            )
            self._tsl_responses[request_id] = None
            self._tsl_pending_requests[request_id].set()
            return

        tsl_data = payload.get("tsl")
        if tsl_data:
            _LOGGER.debug(
                "Received TSL data on gateway %s: profile=%s, deviceType=%s",
                self.gateway_id,
                tsl_data.get("profile"),
                tsl_data.get("deviceType"),
            )
            self._tsl_responses[request_id] = tsl_data
        else:
            _LOGGER.warning(
                "TSL reply missing 'tsl' field on gateway %s",
                self.gateway_id,
            )
            self._tsl_responses[request_id] = None

        self._tsl_pending_requests[request_id].set()

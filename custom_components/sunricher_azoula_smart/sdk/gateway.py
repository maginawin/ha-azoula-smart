"""API client for Azoula Smart gateway."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import json
import logging
from typing import Any

import paho.mqtt.client as paho_mqtt

try:
    from paho.mqtt.enums import CallbackAPIVersion

    HAS_CALLBACK_API_VERSION = True
except ImportError:
    # paho-mqtt < 2.0.0 doesn't have CallbackAPIVersion
    HAS_CALLBACK_API_VERSION = False  # pyright: ignore[reportConstantRedefinition]

from .const import (
    DEFAULT_MQTT_PORT,
    TOPIC_GATEWAY_PREFIX,
    TOPIC_PLATFORM_APP_PREFIX,
    CallbackEventType,
)
from .exceptions import AzoulaGatewayError

_LOGGER = logging.getLogger(__name__)


class AzoulaGateway:
    """API client for Azoula Smart gateway."""

    def __init__(
        self, host: str, username: str, password: str, gateway_id: str
    ) -> None:
        """Initialize the API client."""
        self._host = host
        self._port = DEFAULT_MQTT_PORT
        self._username = username
        self._password = password
        self._id = gateway_id

        self._sub_topic = f"{TOPIC_PLATFORM_APP_PREFIX}/{self._id}"
        self._pub_topic = f"{TOPIC_GATEWAY_PREFIX}/{self._id}"

        if HAS_CALLBACK_API_VERSION:
            # paho-mqtt >= 2.0.0
            self._mqtt_client = paho_mqtt.Client(
                CallbackAPIVersion.VERSION2,  # pyright: ignore[reportPossiblyUnboundVariable]
                client_id=f"ha_dali_center_{self._id}",
                protocol=paho_mqtt.MQTTv311,
            )
        else:
            # paho-mqtt < 2.0.0
            self._mqtt_client = paho_mqtt.Client(
                client_id=f"ha_dali_center_{self._id}",
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
        }
        self._background_tasks: set[asyncio.Task[None]] = set()

    def register_listener(
        self,
        event_type: CallbackEventType,
        listener: Callable[[str, bool], None],
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
        data: bool,
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
            raise AzoulaGatewayError("Connection timeout", self._id) from err
        except (ConnectionRefusedError, OSError) as err:
            raise AzoulaGatewayError(f"Network error: {err}", self._id) from err

        if self._connect_result == 0:
            _LOGGER.info(
                "Connected to gateway %s at %s:%s",
                self._id,
                self._host,
                self._port,
            )
            return

        if self._connect_result in (4, 5):
            raise AzoulaGatewayError(
                "Authentication failed. Please press the gateway button and retry",
                self._id,
            )

        raise AzoulaGatewayError(
            f"Connection failed with code {self._connect_result}",
            self._id,
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
                self._id,
            )

            self._notify_listeners(CallbackEventType.ONLINE_STATUS, self._id, True)

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
                self._id,
                reason_code,
            )
        else:
            _LOGGER.debug("MQTT disconnected for gateway %s", self._id)

        self._notify_listeners(CallbackEventType.ONLINE_STATUS, self._id, False)

    def _on_message(
        self, client: paho_mqtt.Client, userdata: Any, msg: paho_mqtt.MQTTMessage
    ) -> None:
        try:
            payload_json = json.loads(msg.payload.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            _LOGGER.warning(
                "Invalid JSON in MQTT message from gateway %s: %s",
                self._id,
                msg.payload,
            )
            return

        _LOGGER.debug(
            "Received MQTT message from gateway %s on topic %s: %s",
            self._id,
            msg.topic,
            payload_json,
        )

        cmd = payload_json.get("cmd")
        if not cmd:
            _LOGGER.debug(
                "Received MQTT message without cmd field from gateway %s",
                self._id,
            )
            return

        command_handlers: dict[str, Callable[[dict[str, Any]], None]] = {}

        handler = command_handlers.get(cmd)
        if handler:
            handler(payload_json)
        else:
            _LOGGER.debug("Unhandled command %s from gateway %s", cmd, self._id)

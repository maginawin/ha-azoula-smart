"""API client for Azoula Smart gateway."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import json
import logging
from typing import Any

import paho.mqtt.client as paho_mqtt

# Backward compatibility with paho-mqtt < 2.0.0
try:
    from paho.mqtt.enums import CallbackAPIVersion

    HAS_CALLBACK_API_VERSION = True
except ImportError:
    # paho-mqtt < 2.0.0 doesn't have CallbackAPIVersion
    HAS_CALLBACK_API_VERSION = False  # pyright: ignore[reportConstantRedefinition]

from .const import DEFAULT_MQTT_PORT, TOPIC_GATEWAY_PREFIX, TOPIC_PLATFORM_APP_PREFIX
from .exceptions import AzoulaSmartHubError

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
        if HAS_CALLBACK_API_VERSION:
            # paho-mqtt >= 2.0.0
            self._mqtt_client = paho_mqtt.Client(
                CallbackAPIVersion.VERSION2,  # pyright: ignore[reportPossiblyUnboundVariable]
                client_id=f"ha_dali_center_{self._gateway_id}",
                protocol=paho_mqtt.MQTTv311,
            )
        else:
            # paho-mqtt < 2.0.0
            self._mqtt_client = paho_mqtt.Client(
                client_id=f"ha_dali_center_{self._gateway_id}",
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

        # Callbacks
        self._on_online_status: Callable[[str, bool], None] | None = None

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

            cmd = payload_json.get("cmd")
            if not cmd:
                _LOGGER.warning(
                    "Gateway %s: Received MQTT message without cmd field",
                    self._gateway_id,
                )
                return

            command_handlers: dict[str, Callable[[dict[str, Any]], None]] = {}

            handler = command_handlers.get(cmd)
            if handler:
                handler(payload_json)
            else:
                _LOGGER.debug(
                    "Gateway %s: Unhandled MQTT command '%s', payload: %s",
                    self._gateway_id,
                    cmd,
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

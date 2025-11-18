#!/usr/bin/env python3
"""Test script for Azoula gateway connection and disconnection.

This script tests the basic connectivity of the Azoula Smart gateway using
configuration from .env file.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from pathlib import Path
import sys
from typing import Any

from dotenv import load_dotenv

# Add custom_components to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from custom_components.sunricher_azoula.sdk.const import (  # noqa: E402
    SERVICE_COLOR_MOVE_TO_COLOR,
    SERVICE_COLOR_TEMP_MOVE_TO_COLOR_TEMP,
    SERVICE_LEVEL_MOVE_TO_LEVEL_WITH_ONOFF,
    SERVICE_ONOFF_OFF,
    SERVICE_ONOFF_ON,
    CallbackEventType,
)
from custom_components.sunricher_azoula.sdk.device import AzoulaDevice  # noqa: E402
from custom_components.sunricher_azoula.sdk.gateway import AzoulaGateway  # noqa: E402
from custom_components.sunricher_azoula.sdk.types import PropertyParams  # noqa: E402

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

_LOGGER = logging.getLogger(__name__)

# Disable paho.mqtt.client debug logging
logging.getLogger("paho.mqtt.client").setLevel(logging.WARNING)


class GatewayTester:
    """Test class for gateway connection operations."""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        gateway_id: str,
    ) -> None:
        """Initialize the gateway tester."""
        self.host = host
        self.username = username
        self.password = password
        self.gateway_id = gateway_id
        self.gateway: AzoulaGateway | None = None
        self.online_status_events: list[tuple[str, bool]] = []
        self.property_update_events: list[tuple[str, PropertyParams]] = []

        # Device discovery cache
        self.discovered_devices: list[AzoulaDevice] = []
        self.test_light: AzoulaDevice | None = None
        self.test_occupancy_sensor: AzoulaDevice | None = None
        self.test_illuminance_sensor: AzoulaDevice | None = None

        # Event waiting support
        self._pending_online_status: bool | None = None
        self._online_status_event = asyncio.Event()
        self._pending_property_device_id: str | None = None
        self._pending_property_names: set[str] | None = None
        self._property_update_event = asyncio.Event()
        self._last_property_params: PropertyParams | None = None

    def _on_online_status(self, dev_id: str, is_online: bool) -> None:
        """Callback for online status changes."""
        status = "online" if is_online else "offline"
        _LOGGER.info("Gateway %s is now %s", dev_id, status)
        self.online_status_events.append((dev_id, is_online))

        # Trigger event if waiting for this status
        if self._pending_online_status is not None:
            if is_online == self._pending_online_status:
                self._online_status_event.set()

    def _on_property_update(self, dev_id: str, params: PropertyParams) -> None:
        """Callback for property updates."""
        _LOGGER.info("Property update for device %s: %s", dev_id, params)
        self.property_update_events.append((dev_id, params))

        # Trigger event if waiting for this device's property update
        if self._pending_property_device_id == dev_id:
            # If specific properties are being waited for, only trigger if any match
            if self._pending_property_names is not None:
                if any(prop in params for prop in self._pending_property_names):
                    self._last_property_params = params
                    self._property_update_event.set()
            else:
                # No specific properties, trigger on any update
                self._last_property_params = params
                self._property_update_event.set()

    def _write_json_file(self, file_path: Path, data: Any) -> None:
        """Write JSON data to file (blocking operation for use with to_thread)."""
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    async def _wait_for_online_status(
        self, expected_status: bool, timeout_seconds: float = 5.0
    ) -> bool:
        """Wait for online status change with timeout."""
        self._pending_online_status = expected_status
        self._online_status_event.clear()

        try:
            await asyncio.wait_for(
                self._online_status_event.wait(), timeout=timeout_seconds
            )
        except TimeoutError:
            _LOGGER.warning("Timeout waiting for online status %s", expected_status)
            return False
        else:
            return True
        finally:
            self._pending_online_status = None

    async def _wait_for_property_update(
        self,
        device_id: str,
        timeout_seconds: float = 5.0,
        property_names: list[str] | None = None,
    ) -> PropertyParams | None:
        """Wait for property update for specific device with timeout.

        Args:
            device_id: Device ID to wait for
            timeout_seconds: Timeout in seconds
            property_names: Optional list of specific property names to wait for.
                          If provided, only updates containing at least one of these
                          properties will trigger the event. If None, any property
                          update will trigger.

        Returns:
            PropertyParams dict if update received, None on timeout
        """
        self._pending_property_device_id = device_id
        self._pending_property_names = set(property_names) if property_names else None
        self._property_update_event.clear()
        self._last_property_params = None

        try:
            await asyncio.wait_for(
                self._property_update_event.wait(), timeout=timeout_seconds
            )
        except TimeoutError:
            if property_names:
                _LOGGER.warning(
                    "Timeout waiting for properties %s update for device %s",
                    property_names,
                    device_id,
                )
            else:
                _LOGGER.warning(
                    "Timeout waiting for property update for device %s", device_id
                )
            return None
        else:
            return self._last_property_params
        finally:
            self._pending_property_device_id = None
            self._pending_property_names = None

    async def test_connection(self) -> bool:
        """Test connecting to the gateway."""
        _LOGGER.info("=" * 60)
        _LOGGER.info("Test 1: Connection Test")
        _LOGGER.info("=" * 60)

        try:
            self.gateway = AzoulaGateway(
                host=self.host,
                username=self.username,
                password=self.password,
                gateway_id=self.gateway_id,
            )

            # Register callbacks before connecting
            self.gateway.register_listener(
                CallbackEventType.ONLINE_STATUS,
                self._on_online_status,
            )
            self.gateway.register_listener(
                CallbackEventType.PROPERTY_UPDATE,
                self._on_property_update,
            )

            _LOGGER.info(
                "Connecting to gateway %s at %s...", self.gateway_id, self.host
            )
            await self.gateway.connect()
        except Exception:
            _LOGGER.exception("✗ Connection test FAILED")
            return False
        else:
            _LOGGER.info("✓ Connection test PASSED")
            return True

    async def test_disconnection(self) -> bool:
        """Test disconnecting from the gateway."""
        _LOGGER.info("=" * 60)
        _LOGGER.info("Test 2: Disconnection Test")
        _LOGGER.info("=" * 60)

        if not self.gateway:
            _LOGGER.error("✗ Disconnection test FAILED: No gateway instance")
            return False

        try:
            _LOGGER.info("Disconnecting from gateway %s...", self.gateway_id)
            await self.gateway.disconnect()
        except Exception:
            _LOGGER.exception("✗ Disconnection test FAILED")
            return False
        else:
            _LOGGER.info("✓ Disconnection test PASSED")
            return True

    async def test_reconnection(self) -> bool:
        """Test reconnecting to the gateway."""
        _LOGGER.info("=" * 60)
        _LOGGER.info("Test 3: Reconnection Test")
        _LOGGER.info("=" * 60)

        if not self.gateway:
            _LOGGER.error("✗ Reconnection test FAILED: No gateway instance")
            return False

        try:
            _LOGGER.info("Reconnecting to gateway %s...", self.gateway_id)
            await self.gateway.connect()
        except Exception:
            _LOGGER.exception("✗ Reconnection test FAILED")
            return False
        else:
            _LOGGER.info("✓ Reconnection test PASSED")
            return True

    async def test_device_discovery(self) -> bool:
        """Test device discovery."""
        _LOGGER.info("=" * 60)
        _LOGGER.info("Test 4: Device Discovery Test")
        _LOGGER.info("=" * 60)

        if not self.gateway:
            _LOGGER.error("✗ Device discovery test FAILED: No gateway instance")
            return False

        try:
            _LOGGER.info("Discovering devices from gateway %s...", self.gateway_id)

            # Discover devices and cache the results (now returns list of AzoulaDevice)
            self.discovered_devices = await self.gateway.discover_devices()

            # Categorize devices by their capabilities
            lights = [d for d in self.discovered_devices if d.has_property("OnOff")]
            _LOGGER.info("Found %d light(s):", len(lights))
            for light in lights:
                online_status = "online" if light.online else "offline"
                _LOGGER.info(
                    "  - %s (%s) [%s] - %s",
                    light.device_id,
                    light.product_id,
                    light.protocol,
                    online_status,
                )

            # Cache the first light for subsequent tests
            if lights:
                self.test_light = lights[0]

            occupancy_sensors = [
                d for d in self.discovered_devices if d.has_property("OccupancyState")
            ]
            _LOGGER.info("Found %d occupancy sensor(s):", len(occupancy_sensors))
            for sensor in occupancy_sensors:
                online_status = "online" if sensor.online else "offline"
                _LOGGER.info(
                    "  - %s (%s) [%s] - %s",
                    sensor.device_id,
                    sensor.product_id,
                    sensor.protocol,
                    online_status,
                )

            # Cache the first occupancy sensor for subsequent tests
            if occupancy_sensors:
                self.test_occupancy_sensor = occupancy_sensors[0]

            illuminance_sensors = [
                d
                for d in self.discovered_devices
                if d.has_property("IllumMeasuredValue")
            ]
            _LOGGER.info("Found %d illuminance sensor(s):", len(illuminance_sensors))
            for sensor in illuminance_sensors:
                online_status = "online" if sensor.online else "offline"
                _LOGGER.info(
                    "  - %s (%s) [%s] - %s",
                    sensor.device_id,
                    sensor.product_id,
                    sensor.protocol,
                    online_status,
                )

            # Cache the first illuminance sensor for subsequent tests
            if illuminance_sensors:
                self.test_illuminance_sensor = illuminance_sensors[0]

        except Exception:
            _LOGGER.exception("✗ Device discovery test FAILED")
            return False
        else:
            _LOGGER.info("✓ Device discovery test PASSED")
            return True

    async def test_light_control(self) -> bool:
        """Test light control via service invocation."""
        _LOGGER.info("=" * 60)
        _LOGGER.info("Test 5: Light Control Test")
        _LOGGER.info("=" * 60)

        if not self.gateway:
            _LOGGER.error("✗ Light control test FAILED: No gateway instance")
            return False

        try:
            # Use cached light from discovery test
            if not self.test_light:
                _LOGGER.warning("No lights found, skipping light control test")
                return True

            _LOGGER.info(
                "Testing with light: %s (%s)",
                self.test_light.device_id,
                self.test_light.product_id,
            )

            # Clear previous property update events
            initial_events_count = len(self.property_update_events)

            # Test turning on
            _LOGGER.info("Turning light ON...")
            await self.gateway.invoke_service(
                self.test_light.device_id,
                SERVICE_ONOFF_ON,
            )
            await self._wait_for_property_update(
                self.test_light.device_id, timeout_seconds=3.0
            )

            # Test turning off
            _LOGGER.info("Turning light OFF...")
            await self.gateway.invoke_service(
                self.test_light.device_id,
                SERVICE_ONOFF_OFF,
            )
            await self._wait_for_property_update(
                self.test_light.device_id, timeout_seconds=3.0
            )

            # Check if we received property updates
            new_events = len(self.property_update_events) - initial_events_count
            _LOGGER.info("Received %d property update(s) during test", new_events)

        except Exception:
            _LOGGER.exception("✗ Light control test FAILED")
            return False
        else:
            _LOGGER.info("✓ Light control test PASSED")
            return True

    async def test_property_get(self) -> bool:
        """Test property get service."""
        _LOGGER.info("=" * 60)
        _LOGGER.info("Test 6: Property Get Test")
        _LOGGER.info("=" * 60)

        if not self.gateway:
            _LOGGER.error("✗ Property get test FAILED: No gateway instance")
            return False

        try:
            # Use cached light from discovery test
            if not self.test_light:
                _LOGGER.warning("No lights found, skipping property get test")
                return True

            _LOGGER.info(
                "Getting properties for light: %s (%s)",
                self.test_light.device_id,
                self.test_light.product_id,
            )

            # Build property list based on device TSL capabilities
            properties = ["OnOff", "CurrentLevel"]
            if self.test_light.has_property("ColorTemperature"):
                properties.append("ColorTemperature")
            if self.test_light.has_property(
                "CurrentX"
            ) and self.test_light.has_property("CurrentY"):
                properties.extend(["CurrentX", "CurrentY"])

            _LOGGER.info("Requesting properties: %s", properties)
            await self.gateway.get_device_properties(
                self.test_light.device_id,
                properties,
            )

            # Wait for property update using event
            params = await self._wait_for_property_update(
                self.test_light.device_id, timeout_seconds=3.0
            )

            if params:
                _LOGGER.info("Properties received for %s:", self.test_light.device_id)
                for prop_name, prop_data in params.items():
                    if isinstance(prop_data, dict) and "value" in prop_data:
                        _LOGGER.info("  - %s: %s", prop_name, prop_data["value"])  # pyright: ignore[reportUnknownArgumentType]
            else:
                _LOGGER.warning(
                    "No property update events recorded for property get test"
                )

        except Exception:
            _LOGGER.exception("✗ Property get test FAILED")
            return False
        else:
            _LOGGER.info("✓ Property get test PASSED")
            return True

    async def test_light_level_with_onoff(self) -> bool:
        """Test light brightness service with on/off transition."""
        _LOGGER.info("=" * 60)
        _LOGGER.info("Test 7: Light Level With OnOff Test")
        _LOGGER.info("=" * 60)

        if not self.gateway:
            _LOGGER.error("✗ Light level test FAILED: No gateway instance")
            return False

        try:
            # Use cached light from discovery test
            if not self.test_light:
                _LOGGER.warning("No lights found, skipping brightness test")
                return True

            _LOGGER.info(
                "Setting brightness for light: %s (%s)",
                self.test_light.device_id,
                self.test_light.product_id,
            )

            level_params = {
                "Level": 50,
                "TransitionTime": 10,
            }

            _LOGGER.info(
                "Invoking %s with params %s",
                SERVICE_LEVEL_MOVE_TO_LEVEL_WITH_ONOFF,
                level_params,
            )
            await self.gateway.invoke_service(
                self.test_light.device_id,
                SERVICE_LEVEL_MOVE_TO_LEVEL_WITH_ONOFF,
                level_params,
            )

            # Wait for property update using event
            params = await self._wait_for_property_update(
                self.test_light.device_id, timeout_seconds=3.0
            )

            if params:
                current_level = params.get("CurrentLevel")
                if current_level is not None:
                    _LOGGER.info(
                        "Received brightness update for %s: %s",
                        self.test_light.device_id,
                        current_level.get("value"),
                    )
                else:
                    _LOGGER.warning(
                        "No brightness value in property update for %s",
                        self.test_light.device_id,
                    )
            else:
                _LOGGER.warning(
                    "No property update events recorded for brightness test"
                )

        except Exception:
            _LOGGER.exception("✗ Light level test FAILED")
            return False
        else:
            _LOGGER.info("✓ Light level test PASSED")
            return True

    async def test_light_color_temperature(self) -> bool:
        """Test light color temperature control."""
        _LOGGER.info("=" * 60)
        _LOGGER.info("Test 8: Light Color Temperature Test")
        _LOGGER.info("=" * 60)

        if not self.gateway:
            _LOGGER.error("✗ Light color temperature test FAILED: No gateway instance")
            return False

        try:
            # Use cached light from discovery test
            if not self.test_light:
                _LOGGER.warning("No lights found, skipping color temperature test")
                return True

            _LOGGER.info(
                "Setting color temperature for light: %s (%s)",
                self.test_light.device_id,
                self.test_light.product_id,
            )

            color_temp_params = {
                "ColorTemperature": 3500,
                "TransitionTime": 10,
            }

            _LOGGER.info(
                "Invoking %s with params %s",
                SERVICE_COLOR_TEMP_MOVE_TO_COLOR_TEMP,
                color_temp_params,
            )
            await self.gateway.invoke_service(
                self.test_light.device_id,
                SERVICE_COLOR_TEMP_MOVE_TO_COLOR_TEMP,
                color_temp_params,
            )

            # Wait for property update using event
            params = await self._wait_for_property_update(
                self.test_light.device_id, timeout_seconds=3.0
            )

            if params:
                color_temp = params.get("ColorTemperature")
                current_x = params.get("CurrentX")
                current_y = params.get("CurrentY")

                if color_temp is not None:
                    _LOGGER.info(
                        "Received color temperature update for %s: %s",
                        self.test_light.device_id,
                        color_temp.get("value"),
                    )
                else:
                    _LOGGER.warning(
                        "No color temperature value in property update for %s",
                        self.test_light.device_id,
                    )

                if current_x is not None or current_y is not None:
                    _LOGGER.info(
                        "Received color XY update for %s: (%s, %s)",
                        self.test_light.device_id,
                        current_x.get("value") if current_x else None,
                        current_y.get("value") if current_y else None,
                    )
            else:
                _LOGGER.warning(
                    "No property update events recorded for color temperature test"
                )

        except Exception:
            _LOGGER.exception("✗ Light color temperature test FAILED")
            return False
        else:
            _LOGGER.info("✓ Light color temperature test PASSED")
            return True

    async def test_light_color_xy(self) -> bool:
        """Test light XY color control."""
        _LOGGER.info("=" * 60)
        _LOGGER.info("Test 9: Light Color XY Test")
        _LOGGER.info("=" * 60)

        if not self.gateway:
            _LOGGER.error("✗ Light color XY test FAILED: No gateway instance")
            return False

        try:
            # Use cached light from discovery test
            if not self.test_light:
                _LOGGER.warning("No lights found, skipping color XY test")
                return True

            _LOGGER.info(
                "Setting XY color for light: %s (%s)",
                self.test_light.device_id,
                self.test_light.product_id,
            )

            color_xy_params: dict[str, float] = {
                "ColorX": 0.4,
                "ColorY": 0.5,
                "TransitionTime": 10,
            }

            _LOGGER.info(
                "Invoking %s with params %s",
                SERVICE_COLOR_MOVE_TO_COLOR,
                color_xy_params,
            )
            await self.gateway.invoke_service(
                self.test_light.device_id,
                SERVICE_COLOR_MOVE_TO_COLOR,
                color_xy_params,
            )

            # Wait for property update using event
            params = await self._wait_for_property_update(
                self.test_light.device_id, timeout_seconds=3.0
            )

            if params:
                current_x = params.get("CurrentX")
                current_y = params.get("CurrentY")
                color_temp = params.get("ColorTemperature")

                if current_x is not None or current_y is not None:
                    _LOGGER.info(
                        "Received color XY update for %s: (%s, %s)",
                        self.test_light.device_id,
                        current_x.get("value") if current_x else None,
                        current_y.get("value") if current_y else None,
                    )
                else:
                    _LOGGER.warning(
                        "No color XY value in property update for %s",
                        self.test_light.device_id,
                    )

                if color_temp is not None:
                    _LOGGER.info(
                        "Received color temperature update for %s while setting XY: %s",
                        self.test_light.device_id,
                        color_temp.get("value"),
                    )
            else:
                _LOGGER.warning("No property update events recorded for color XY test")

        except Exception:
            _LOGGER.exception("✗ Light color XY test FAILED")
            return False
        else:
            _LOGGER.info("✓ Light color XY test PASSED")
            return True

    async def test_illuminance_sensor_monitoring(self) -> bool:
        """Test illuminance sensor property monitoring."""
        _LOGGER.info("=" * 60)
        _LOGGER.info("Test 10: Illuminance Sensor Monitoring Test")
        _LOGGER.info("=" * 60)

        if not self.gateway:
            _LOGGER.error(
                "✗ Illuminance sensor monitoring test FAILED: No gateway instance"
            )
            return False

        try:
            # Use cached illuminance sensor from discovery test
            if not self.test_illuminance_sensor:
                _LOGGER.warning(
                    "No illuminance sensors found, skipping illuminance sensor test"
                )
                return True

            _LOGGER.info(
                "Monitoring illuminance sensor: %s (%s)",
                self.test_illuminance_sensor.device_id,
                self.test_illuminance_sensor.product_id,
            )

            # Request current property values
            properties = ["IllumMeasuredValue"]

            _LOGGER.info("Requesting properties: %s", properties)
            await self.gateway.get_device_properties(
                self.test_illuminance_sensor.device_id,
                properties,
            )

            # Wait for property update using event
            params = await self._wait_for_property_update(
                self.test_illuminance_sensor.device_id, timeout_seconds=3.0
            )

            if params:
                _LOGGER.info(
                    "Properties received for %s:",
                    self.test_illuminance_sensor.device_id,
                )
                for prop_name, prop_data in params.items():
                    if isinstance(prop_data, dict) and "value" in prop_data:
                        value = prop_data["value"]  # pyright: ignore[reportUnknownVariableType]
                        _LOGGER.info("  - %s: %s Lux", prop_name, value)  # pyright: ignore[reportUnknownArgumentType]
            else:
                _LOGGER.warning(
                    "No property update events recorded for illuminance sensor test"
                )

            _LOGGER.info(
                "Illuminance sensor is now being monitored. "
                "Any illuminance changes will trigger property updates."
            )

        except Exception:
            _LOGGER.exception("✗ Illuminance sensor monitoring test FAILED")
            return False
        else:
            _LOGGER.info("✓ Illuminance sensor monitoring test PASSED")
            return True

    async def test_device_tsl(self) -> bool:
        """Test device TSL (Thing Specification Language) retrieval for all devices."""
        _LOGGER.info("=" * 60)
        _LOGGER.info("Test 11: Device TSL Retrieval Test")
        _LOGGER.info("=" * 60)

        if not self.gateway:
            _LOGGER.error("✗ Device TSL test FAILED: No gateway instance")
            return False

        # Create doc directory for TSL files
        doc_dir = project_root / "doc" / "tsl"
        doc_dir.mkdir(parents=True, exist_ok=True)
        _LOGGER.info("TSL files will be saved to: %s", doc_dir)
        _LOGGER.info("")

        if not self.discovered_devices:
            _LOGGER.warning("No devices found to test TSL retrieval")
            return True

        try:
            _LOGGER.info(
                "Getting TSL for all %d discovered devices...",
                len(self.discovered_devices),
            )
            _LOGGER.info("")

            success_count = 0

            for device in self.discovered_devices:
                device_name = device.name if device.name else "(unnamed)"
                product_display = (
                    device.product_id if device.product_id else "(no product_id)"
                )
                _LOGGER.info(
                    "Getting TSL for device: %s",
                    device.device_id,
                )
                _LOGGER.info("  - Name: %s", device_name)
                _LOGGER.info("  - Product: %s", product_display)
                _LOGGER.info("  - Protocol: %s", device.protocol)

                # Check if TSL file already exists
                safe_filename = (
                    device.device_id.replace("/", "_")
                    .replace("\\", "_")
                    .replace(":", "_")
                )
                tsl_file = doc_dir / f"{safe_filename}.json"
                if tsl_file.exists():
                    _LOGGER.info("  - TSL file already exists: %s, skipping", tsl_file.name)
                    _LOGGER.info("")
                    success_count += 1
                    continue

                tsl = await self.gateway.get_device_tsl(device.device_id)

                if tsl:
                    _LOGGER.info("✓ TSL received:")
                    _LOGGER.info("  - Profile: %s", tsl.get("profile"))
                    _LOGGER.info("  - DeviceType: %s", tsl.get("deviceType"))
                    _LOGGER.info("  - Properties: %d", len(tsl.get("properties", [])))
                    _LOGGER.info("  - Services: %d", len(tsl.get("services", [])))
                    _LOGGER.info("  - Events: %d", len(tsl.get("events", [])))

                    # Log some property details
                    properties = tsl.get("properties", [])
                    if properties:
                        _LOGGER.info("  - Properties:")
                        for prop in properties:
                            _LOGGER.info(
                                "    * %s (%s): %s",
                                prop.get("identifier"),
                                prop.get("name"),
                                prop.get("accessMode"),
                            )

                    # Save TSL to JSON file using device_id as filename
                    # This ensures each device gets its own file
                    await asyncio.to_thread(self._write_json_file, tsl_file, tsl)
                    _LOGGER.info("  - Saved to: %s", tsl_file.name)

                    success_count += 1
                else:
                    _LOGGER.warning("No TSL received for device %s", device.device_id)

                _LOGGER.info("")

            _LOGGER.info(
                "TSL retrieval complete: %d/%d devices processed",
                success_count,
                len(self.discovered_devices),
            )

        except Exception:
            _LOGGER.exception("✗ Device TSL test FAILED")
            return False
        else:
            _LOGGER.info("✓ Device TSL test PASSED")
            return True

    async def test_occupancy_sensor_monitoring(self) -> bool:
        """Test occupancy sensor property monitoring."""
        _LOGGER.info("=" * 60)
        _LOGGER.info("Test 12: Occupancy Sensor Monitoring Test")
        _LOGGER.info("=" * 60)

        if not self.gateway:
            _LOGGER.error(
                "✗ Occupancy sensor monitoring test FAILED: No gateway instance"
            )
            return False

        try:
            # Use cached occupancy sensor from discovery test
            if not self.test_occupancy_sensor:
                _LOGGER.warning(
                    "No occupancy sensors found, skipping occupancy sensor test"
                )
                return True

            _LOGGER.info(
                "Monitoring occupancy sensor: %s (%s)",
                self.test_occupancy_sensor.device_id,
                self.test_occupancy_sensor.product_id,
            )

            # Request current property values
            properties = ["OccupancyState"]

            _LOGGER.info("Requesting properties: %s", properties)
            await self.gateway.get_device_properties(
                self.test_occupancy_sensor.device_id,
                properties,
            )

            # Wait for property update using event
            params = await self._wait_for_property_update(
                self.test_occupancy_sensor.device_id, timeout_seconds=3.0
            )

            if params:
                _LOGGER.info(
                    "Properties received for %s:", self.test_occupancy_sensor.device_id
                )
                for prop_name, prop_data in params.items():
                    if isinstance(prop_data, dict) and "value" in prop_data:
                        value = prop_data["value"]  # pyright: ignore[reportUnknownVariableType]
                        status = "occupied" if value == 1 else "unoccupied"
                        _LOGGER.info("  - %s: %s (%s)", prop_name, value, status)  # pyright: ignore[reportUnknownArgumentType]
            else:
                _LOGGER.warning(
                    "No property update events recorded for occupancy sensor test"
                )

            _LOGGER.info(
                "Occupancy sensor is now being monitored. "
                "Any occupancy changes will trigger property updates."
            )

        except Exception:
            _LOGGER.exception("✗ Occupancy sensor monitoring test FAILED")
            return False
        else:
            _LOGGER.info("✓ Occupancy sensor monitoring test PASSED")
            return True

    async def test_device_identify(self) -> bool:
        """Test device identify functionality."""
        _LOGGER.info("=" * 60)
        _LOGGER.info("Test 13: Device Identify Test")
        _LOGGER.info("=" * 60)

        if not self.gateway:
            _LOGGER.error("✗ Device identify test FAILED: No gateway instance")
            return False

        try:
            # Test identify on all discovered devices that support it
            devices_with_identify = [
                d for d in self.discovered_devices if d.has_identify_support()
            ]

            if not devices_with_identify:
                _LOGGER.warning(
                    "No devices with identify support found, skipping identify test"
                )
                return True

            _LOGGER.info(
                "Found %d device(s) with identify support", len(devices_with_identify)
            )

            for device in devices_with_identify:
                _LOGGER.info(
                    "Testing identify for device: %s (%s)",
                    device.device_id,
                    device.product_id,
                )
                _LOGGER.info("  - Name: %s", device.name)
                _LOGGER.info("  - Protocol: %s", device.protocol)

                # Trigger identify
                await self.gateway.identify_device(device.device_id)

                _LOGGER.info(
                    "✓ Identify command sent to device %s (device should flash/blink)",
                    device.device_id,
                )
                _LOGGER.info("")

                # Small delay between devices
                await asyncio.sleep(1)

        except Exception:
            _LOGGER.exception("✗ Device identify test FAILED")
            return False
        else:
            _LOGGER.info("✓ Device identify test PASSED")
            return True

    async def test_configuration_property_get(self) -> bool:
        """Test getting configuration properties (StartUpOnOff, TransitionTime, etc.)."""
        _LOGGER.info("=" * 60)
        _LOGGER.info("Test 14: Configuration Property Get Test")
        _LOGGER.info("=" * 60)

        if not self.gateway:
            _LOGGER.error(
                "✗ Configuration property get test FAILED: No gateway instance"
            )
            return False

        try:
            # Use cached light from discovery test
            if not self.test_light:
                _LOGGER.warning("No lights found, skipping configuration property test")
                return True

            _LOGGER.info(
                "Getting configuration properties for light: %s (%s)",
                self.test_light.device_id,
                self.test_light.product_id,
            )

            # Build property list based on device TSL capabilities
            properties = []
            if self.test_light.has_property("StartUpOnOff"):
                properties.append("StartUpOnOff")
            if self.test_light.has_property("OnOffTransitionTime"):
                properties.append("OnOffTransitionTime")
            if self.test_light.has_property("OnTransitionTime"):
                properties.append("OnTransitionTime")
            if self.test_light.has_property("OffTransitionTime"):
                properties.append("OffTransitionTime")
            if self.test_light.has_property("MinLevelSet"):
                properties.append("MinLevelSet")
            if self.test_light.has_property("CurrentSummationDelivered"):
                properties.append("CurrentSummationDelivered")
            if self.test_light.has_property("ActivePower_User"):
                properties.append("ActivePower_User")

            if not properties:
                _LOGGER.warning(
                    "No configuration properties found for device %s",
                    self.test_light.device_id,
                )
                return True

            _LOGGER.info("Requesting configuration properties: %s", properties)
            await self.gateway.get_device_properties(
                self.test_light.device_id,
                properties,
            )

            # Wait for property update using event
            params = await self._wait_for_property_update(
                self.test_light.device_id, timeout_seconds=3.0
            )

            if params:
                _LOGGER.info(
                    "Configuration properties received for %s:",
                    self.test_light.device_id,
                )
                for prop_name, prop_data in params.items():
                    if isinstance(prop_data, dict) and "value" in prop_data:
                        value = prop_data["value"]  # pyright: ignore[reportUnknownVariableType]
                        # Add unit information for known properties
                        if prop_name in (
                            "OnOffTransitionTime",
                            "OnTransitionTime",
                            "OffTransitionTime",
                        ):
                            _LOGGER.info(
                                "  - %s: %s (0.1s units = %.1f seconds)",
                                prop_name,
                                value,
                                float(value) / 10.0,
                            )  # pyright: ignore[reportUnknownArgumentType]
                        elif prop_name == "StartUpOnOff":
                            status_map = {
                                0: "off",
                                1: "on",
                                2: "toggle",
                                255: "previous",
                            }
                            status_str = status_map.get(int(value), "unknown")  # pyright: ignore[reportUnknownArgumentType]
                            _LOGGER.info(
                                "  - %s: %s (%s)", prop_name, value, status_str
                            )  # pyright: ignore[reportUnknownArgumentType]
                        elif prop_name == "CurrentSummationDelivered":
                            _LOGGER.info("  - %s: %s kWh", prop_name, value)  # pyright: ignore[reportUnknownArgumentType]
                        elif prop_name == "ActivePower_User":
                            _LOGGER.info("  - %s: %s W", prop_name, value)  # pyright: ignore[reportUnknownArgumentType]
                        else:
                            _LOGGER.info("  - %s: %s", prop_name, value)  # pyright: ignore[reportUnknownArgumentType]
            else:
                _LOGGER.warning(
                    "No property update events recorded for configuration property get test"
                )

        except Exception:
            _LOGGER.exception("✗ Configuration property get test FAILED")
            return False
        else:
            _LOGGER.info("✓ Configuration property get test PASSED")
            return True

    async def test_configuration_property_set(self) -> bool:
        """Test setting configuration properties (StartUpOnOff, MinLevelSet, TransitionTime)."""
        _LOGGER.info("=" * 60)
        _LOGGER.info("Test 15: Configuration Property Set Test")
        _LOGGER.info("=" * 60)

        if not self.gateway:
            _LOGGER.error(
                "✗ Configuration property set test FAILED: No gateway instance"
            )
            return False

        try:
            # Use cached light from discovery test
            if not self.test_light:
                _LOGGER.warning(
                    "No lights found, skipping configuration property set test"
                )
                return True

            _LOGGER.info(
                "Setting configuration properties for light: %s (%s)",
                self.test_light.device_id,
                self.test_light.product_id,
            )

            # Track verification failures
            verification_failures = 0

            # Test setting StartUpOnOff (power-on behavior)
            if self.test_light.has_property("StartUpOnOff"):
                _LOGGER.info("Testing StartUpOnOff property set...")

                # First, get current value
                await self.gateway.get_device_properties(
                    self.test_light.device_id,
                    ["StartUpOnOff"],
                )
                params = await self._wait_for_property_update(
                    self.test_light.device_id, timeout_seconds=3.0
                )
                original_value = 255  # Default to "previous"
                if params and "StartUpOnOff" in params:
                    original_value = int(params["StartUpOnOff"]["value"])  # pyright: ignore[reportUnknownArgumentType]
                    _LOGGER.info("  - Current StartUpOnOff: %s", original_value)

                # Set to a different value (toggle between 0/off and 255/previous)
                new_value = 0 if original_value == 255 else 255
                status_map = {0: "off", 1: "on", 2: "toggle", 255: "previous"}
                _LOGGER.info(
                    "  - Setting StartUpOnOff to %s (%s)",
                    new_value,
                    status_map.get(new_value, "unknown"),
                )

                await self.gateway.set_device_properties(
                    self.test_light.device_id,
                    {"StartUpOnOff": new_value},
                )

                # Wait for confirmation from device property post
                params = await self._wait_for_property_update(
                    self.test_light.device_id, timeout_seconds=3.0
                )
                if params and "StartUpOnOff" in params:
                    confirmed_value = params["StartUpOnOff"]["value"]  # pyright: ignore[reportUnknownVariableType]
                    _LOGGER.info(
                        "  - Property post confirmation: %s", confirmed_value
                    )  # pyright: ignore[reportUnknownArgumentType]
                else:
                    _LOGGER.warning("  - No property post confirmation received")

                # Verify by re-reading the property
                _LOGGER.info("  - Verifying by re-reading property...")
                await self.gateway.get_device_properties(
                    self.test_light.device_id,
                    ["StartUpOnOff"],
                )
                params = await self._wait_for_property_update(
                    self.test_light.device_id,
                    timeout_seconds=3.0,
                    property_names=["StartUpOnOff"],
                )
                if params and "StartUpOnOff" in params:
                    verified_value = int(params["StartUpOnOff"]["value"])  # pyright: ignore[reportUnknownArgumentType]
                    if verified_value == new_value:
                        _LOGGER.info(
                            "  ✓ VERIFIED: StartUpOnOff successfully changed to %s",
                            verified_value,
                        )
                    else:
                        _LOGGER.error(
                            "  ✗ VERIFICATION FAILED: Expected %s, got %s",
                            new_value,
                            verified_value,
                        )
                        verification_failures += 1
                else:
                    _LOGGER.warning("  - Could not verify property change")
                    verification_failures += 1

                # Restore original value
                _LOGGER.info("  - Restoring StartUpOnOff to %s", original_value)
                await self.gateway.set_device_properties(
                    self.test_light.device_id,
                    {"StartUpOnOff": original_value},
                )
                await asyncio.sleep(0.5)

            # Test setting OnOffTransitionTime
            if self.test_light.has_property("OnOffTransitionTime"):
                _LOGGER.info("Testing OnOffTransitionTime property set...")

                # Get current value
                await self.gateway.get_device_properties(
                    self.test_light.device_id,
                    ["OnOffTransitionTime"],
                )
                params = await self._wait_for_property_update(
                    self.test_light.device_id, timeout_seconds=3.0
                )
                original_value = 0
                if params and "OnOffTransitionTime" in params:
                    original_value = int(params["OnOffTransitionTime"]["value"])  # pyright: ignore[reportUnknownArgumentType]
                    _LOGGER.info(
                        "  - Current OnOffTransitionTime: %s (%.1f seconds)",
                        original_value,
                        original_value / 10.0,
                    )

                # Set to 10 (1 second transition)
                new_value = 10
                _LOGGER.info(
                    "  - Setting OnOffTransitionTime to %s (%.1f seconds)",
                    new_value,
                    new_value / 10.0,
                )

                await self.gateway.set_device_properties(
                    self.test_light.device_id,
                    {"OnOffTransitionTime": new_value},
                )

                # Wait for confirmation from device property post
                params = await self._wait_for_property_update(
                    self.test_light.device_id, timeout_seconds=3.0
                )
                if params and "OnOffTransitionTime" in params:
                    confirmed_value = params["OnOffTransitionTime"]["value"]  # pyright: ignore[reportUnknownVariableType]
                    _LOGGER.info(
                        "  - Property post confirmation: %s (%.1f seconds)",
                        confirmed_value,  # pyright: ignore[reportUnknownArgumentType]
                        float(confirmed_value) / 10.0,  # pyright: ignore[reportUnknownArgumentType]
                    )
                else:
                    _LOGGER.warning("  - No property post confirmation received")

                # Verify by re-reading the property
                _LOGGER.info("  - Verifying by re-reading property...")
                await self.gateway.get_device_properties(
                    self.test_light.device_id,
                    ["OnOffTransitionTime"],
                )
                params = await self._wait_for_property_update(
                    self.test_light.device_id,
                    timeout_seconds=3.0,
                    property_names=["OnOffTransitionTime"],
                )
                if params and "OnOffTransitionTime" in params:
                    verified_value = int(params["OnOffTransitionTime"]["value"])  # pyright: ignore[reportUnknownArgumentType]
                    if verified_value == new_value:
                        _LOGGER.info(
                            "  ✓ VERIFIED: OnOffTransitionTime successfully changed to %s (%.1f s)",
                            verified_value,
                            verified_value / 10.0,
                        )
                    else:
                        _LOGGER.error(
                            "  ✗ VERIFICATION FAILED: Expected %s, got %s",
                            new_value,
                            verified_value,
                        )
                        verification_failures += 1
                else:
                    _LOGGER.warning("  - Could not verify property change")
                    verification_failures += 1

                # Restore original value
                _LOGGER.info(
                    "  - Restoring OnOffTransitionTime to %s (%.1f seconds)",
                    original_value,
                    original_value / 10.0,
                )
                await self.gateway.set_device_properties(
                    self.test_light.device_id,
                    {"OnOffTransitionTime": original_value},
                )
                await asyncio.sleep(0.5)

            # Test setting MinLevelSet
            if self.test_light.has_property("MinLevelSet"):
                _LOGGER.info("Testing MinLevelSet property set...")

                # Set minimum brightness to 10
                new_value = 10
                _LOGGER.info("  - Setting MinLevelSet to %s", new_value)

                await self.gateway.set_device_properties(
                    self.test_light.device_id,
                    {"MinLevelSet": new_value},
                )

                # Note: MinLevelSet is write-only (accessMode: "w"), so we may not get a confirmation
                _LOGGER.info(
                    "  - MinLevelSet command sent (write-only property, no confirmation expected)"
                )
                await asyncio.sleep(0.5)

            # Check for verification failures
            if verification_failures > 0:
                _LOGGER.error(
                    "Configuration property set test completed with %d verification failure(s)",
                    verification_failures,
                )
                _LOGGER.info("✗ Configuration property set test FAILED")
                return False

            _LOGGER.info("Configuration property set test completed successfully")

        except Exception:
            _LOGGER.exception("✗ Configuration property set test FAILED")
            return False
        else:
            _LOGGER.info("✓ Configuration property set test PASSED")
            return True

    async def test_energy_monitoring(self) -> bool:
        """Test energy monitoring properties (CurrentSummationDelivered, ActivePower_User)."""
        _LOGGER.info("=" * 60)
        _LOGGER.info("Test 16: Energy Monitoring Test")
        _LOGGER.info("=" * 60)

        if not self.gateway:
            _LOGGER.error("✗ Energy monitoring test FAILED: No gateway instance")
            return False

        try:
            # Find devices with energy monitoring capabilities
            energy_devices = [
                d
                for d in self.discovered_devices
                if d.has_property("CurrentSummationDelivered")
                or d.has_property("ActivePower_User")
            ]

            if not energy_devices:
                _LOGGER.warning(
                    "No devices with energy monitoring found, skipping energy test"
                )
                return True

            _LOGGER.info(
                "Found %d device(s) with energy monitoring capabilities",
                len(energy_devices),
            )

            for device in energy_devices:
                _LOGGER.info(
                    "Testing energy monitoring for device: %s (%s)",
                    device.device_id,
                    device.product_id,
                )

                # Build property list
                properties: list[str] = []
                if device.has_property("CurrentSummationDelivered"):
                    properties.append("CurrentSummationDelivered")
                if device.has_property("ActivePower_User"):
                    properties.append("ActivePower_User")
                if device.has_property("StandbyPower_User"):
                    properties.append("StandbyPower_User")

                _LOGGER.info("  - Requesting properties: %s", properties)
                await self.gateway.get_device_properties(
                    device.device_id,
                    properties,
                )

                # Wait for property update
                params = await self._wait_for_property_update(
                    device.device_id, timeout_seconds=3.0
                )

                if params:
                    _LOGGER.info("  - Energy properties received:")
                    if "CurrentSummationDelivered" in params:
                        value = params["CurrentSummationDelivered"]["value"]  # pyright: ignore[reportUnknownVariableType]
                        _LOGGER.info("    * Total Energy: %s kWh", value)  # pyright: ignore[reportUnknownArgumentType]
                    if "ActivePower_User" in params:
                        value = params["ActivePower_User"]["value"]  # pyright: ignore[reportUnknownVariableType]
                        _LOGGER.info("    * Active Power: %s W", value)  # pyright: ignore[reportUnknownArgumentType]
                    if "StandbyPower_User" in params:
                        value = params["StandbyPower_User"]["value"]  # pyright: ignore[reportUnknownVariableType]
                        _LOGGER.info("    * Standby Power: %s W", value)  # pyright: ignore[reportUnknownArgumentType]
                else:
                    _LOGGER.warning(
                        "  - No property update received for device %s",
                        device.device_id,
                    )

                _LOGGER.info("")

        except Exception:
            _LOGGER.exception("✗ Energy monitoring test FAILED")
            return False
        else:
            _LOGGER.info("✓ Energy monitoring test PASSED")
            return True

    async def run_all_tests(self) -> None:
        """Run all connection tests."""
        _LOGGER.info("Starting Azoula Gateway Connection Tests")
        _LOGGER.info("Host: %s", self.host)
        _LOGGER.info("Gateway ID: %s", self.gateway_id)
        _LOGGER.info("")

        results: list[tuple[str, bool]] = []

        try:
            # Test 1: Initial connection
            result = await self.test_connection()
            results.append(("Connection", result))

            if not result:
                _LOGGER.error("Connection test failed, aborting remaining tests")
                return

            # Test 2: Disconnection
            result = await self.test_disconnection()
            results.append(("Disconnection", result))

            # Test 3: Reconnection
            result = await self.test_reconnection()
            results.append(("Reconnection", result))

            # Test 4: Device Discovery
            result = await self.test_device_discovery()
            results.append(("Device Discovery", result))

            # Test 5: Light Control
            result = await self.test_light_control()
            results.append(("Light Control", result))

            # Test 6: Property Get
            result = await self.test_property_get()
            results.append(("Property Get", result))

            # Test 7: Light Level With OnOff
            result = await self.test_light_level_with_onoff()
            results.append(("Light Level With OnOff", result))

            # Test 8: Light Color Temperature
            result = await self.test_light_color_temperature()
            results.append(("Light Color Temperature", result))

            # Test 9: Light Color XY
            result = await self.test_light_color_xy()
            results.append(("Light Color XY", result))

            # Test 10: Illuminance Sensor Monitoring
            result = await self.test_illuminance_sensor_monitoring()
            results.append(("Illuminance Sensor Monitoring", result))

            # Test 11: Device TSL Retrieval
            result = await self.test_device_tsl()
            results.append(("Device TSL Retrieval", result))

            # Test 12: Occupancy Sensor Monitoring
            result = await self.test_occupancy_sensor_monitoring()
            results.append(("Occupancy Sensor Monitoring", result))

            # Test 13: Device Identify
            result = await self.test_device_identify()
            results.append(("Device Identify", result))

            # Test 14: Configuration Property Get
            result = await self.test_configuration_property_get()
            results.append(("Configuration Property Get", result))

            # Test 15: Configuration Property Set
            result = await self.test_configuration_property_set()
            results.append(("Configuration Property Set", result))

            # Test 16: Energy Monitoring
            result = await self.test_energy_monitoring()
            results.append(("Energy Monitoring", result))

        finally:
            # Cleanup
            if self.gateway:
                try:
                    await self.gateway.disconnect()
                except Exception as err:
                    _LOGGER.debug("Error during cleanup: %s", err)

            # Print summary
            _LOGGER.info("=" * 60)
            _LOGGER.info("Test Summary")
            _LOGGER.info("=" * 60)

            passed = sum(1 for _, result in results if result)
            total = len(results)

            for test_name, result in results:
                status = "✓ PASSED" if result else "✗ FAILED"
                _LOGGER.info("%s: %s", test_name, status)

            _LOGGER.info("")
            _LOGGER.info("Total: %d/%d tests passed", passed, total)
            _LOGGER.info(
                "Online status events received: %d", len(self.online_status_events)
            )
            _LOGGER.info(
                "Property update events received: %d", len(self.property_update_events)
            )


def load_config_from_env() -> dict[str, str]:
    """Load configuration from .env file."""
    # Load .env file
    env_path = project_root / ".env"
    if not env_path.exists():
        _LOGGER.warning(".env file not found at %s", env_path)
        _LOGGER.info("Please copy .env.example to .env and configure your gateway")
        sys.exit(1)

    load_dotenv(env_path)

    # Get required configuration
    config = {
        "host": os.getenv("AZOULA_HOST", ""),
        "username": os.getenv("AZOULA_USERNAME", ""),
        "password": os.getenv("AZOULA_PASSWORD", ""),
        "gateway_id": os.getenv("AZOULA_GATEWAY_ID", ""),
    }

    # Validate configuration
    missing = [key for key, value in config.items() if not value]
    if missing:
        _LOGGER.error("Missing required configuration: %s", ", ".join(missing))
        _LOGGER.info("Please configure these values in .env file")
        sys.exit(1)

    return config


def main() -> None:
    """Run the test script."""
    parser = argparse.ArgumentParser(
        description="Test Azoula gateway connection and disconnection"
    )
    parser.add_argument(
        "--host",
        help="Gateway host (overrides .env)",
    )
    parser.add_argument(
        "--username",
        help="Gateway username (overrides .env)",
    )
    parser.add_argument(
        "--password",
        help="Gateway password (overrides .env)",
    )
    parser.add_argument(
        "--gateway-id",
        help="Gateway ID (overrides .env)",
    )

    args = parser.parse_args()

    # Load configuration from .env
    config = load_config_from_env()

    # Override with command line arguments if provided
    if args.host:
        config["host"] = args.host
    if args.username:
        config["username"] = args.username
    if args.password:
        config["password"] = args.password
    if args.gateway_id:
        config["gateway_id"] = args.gateway_id

    # Create tester and run tests
    tester = GatewayTester(
        host=config["host"],
        username=config["username"],
        password=config["password"],
        gateway_id=config["gateway_id"],
    )

    try:
        asyncio.run(tester.run_all_tests())
    except KeyboardInterrupt:
        _LOGGER.info("Tests interrupted by user")
        sys.exit(130)


if __name__ == "__main__":
    main()

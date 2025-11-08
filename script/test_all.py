#!/usr/bin/env python3
"""Test script for Azoula gateway connection and disconnection.

This script tests the basic connectivity of the Azoula Smart gateway using
configuration from .env file.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
from pathlib import Path
import sys
from typing import Any

from dotenv import load_dotenv

# Add custom_components to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from custom_components.sunricher_azoula_smart.sdk.const import (  # noqa: E402
    SERVICE_COLOR_MOVE_TO_COLOR,
    SERVICE_COLOR_TEMP_MOVE_TO_COLOR_TEMP,
    SERVICE_LEVEL_MOVE_TO_LEVEL_WITH_ONOFF,
    SERVICE_ONOFF_OFF,
    SERVICE_ONOFF_ON,
    CallbackEventType,
    DeviceType,
)
from custom_components.sunricher_azoula_smart.sdk.gateway import (  # noqa: E402
    AzoulaGateway,
)
from custom_components.sunricher_azoula_smart.sdk.types import (  # noqa: E402
    PropertyParams,
)

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

_LOGGER = logging.getLogger(__name__)


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
        self.discovered_devices: dict[DeviceType, list[Any]] = {}
        self.test_light: Any = None

        # Event waiting support
        self._pending_online_status: bool | None = None
        self._online_status_event = asyncio.Event()
        self._pending_property_device_id: str | None = None
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
            self._last_property_params = params
            self._property_update_event.set()

    async def _wait_for_online_status(
        self, expected_status: bool, timeout: float = 5.0
    ) -> bool:
        """Wait for online status change with timeout."""
        self._pending_online_status = expected_status
        self._online_status_event.clear()

        try:
            await asyncio.wait_for(self._online_status_event.wait(), timeout=timeout)
            return True
        except TimeoutError:
            _LOGGER.warning("Timeout waiting for online status %s", expected_status)
            return False
        finally:
            self._pending_online_status = None

    async def _wait_for_property_update(
        self, device_id: str, timeout: float = 5.0
    ) -> PropertyParams | None:
        """Wait for property update for specific device with timeout."""
        self._pending_property_device_id = device_id
        self._property_update_event.clear()
        self._last_property_params = None

        try:
            await asyncio.wait_for(self._property_update_event.wait(), timeout=timeout)
            return self._last_property_params
        except TimeoutError:
            _LOGGER.warning(
                "Timeout waiting for property update for device %s", device_id
            )
            return None
        finally:
            self._pending_property_device_id = None

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
            _LOGGER.info("✓ Connection test PASSED")
            return True

        except Exception:
            _LOGGER.exception("✗ Connection test FAILED")
            return False

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
            _LOGGER.info("✓ Disconnection test PASSED")
            return True

        except Exception:
            _LOGGER.exception("✗ Disconnection test FAILED")
            return False

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
            _LOGGER.info("✓ Reconnection test PASSED")
            return True

        except Exception:
            _LOGGER.exception("✗ Reconnection test FAILED")
            return False

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

            # Discover devices and cache the results
            self.discovered_devices = await self.gateway.discover_devices()

            lights = self.discovered_devices.get(DeviceType.LIGHT, [])
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
            await self._wait_for_property_update(self.test_light.device_id, timeout=3.0)

            # Test turning off
            _LOGGER.info("Turning light OFF...")
            await self.gateway.invoke_service(
                self.test_light.device_id,
                SERVICE_ONOFF_OFF,
            )
            await self._wait_for_property_update(self.test_light.device_id, timeout=3.0)

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

            properties = ["OnOff", "CurrentLevel"]
            if (
                "CCT" in self.test_light.product_id
                or "RGBCCT" in self.test_light.product_id
            ):
                properties.append("ColorTemperature")
            if (
                "RGB" in self.test_light.product_id
                or "RGBCCT" in self.test_light.product_id
            ):
                properties.extend(["CurrentX", "CurrentY"])

            _LOGGER.info("Requesting properties: %s", properties)
            await self.gateway.get_device_properties(
                self.test_light.device_id,
                properties,
            )

            # Wait for property update using event
            params = await self._wait_for_property_update(
                self.test_light.device_id, timeout=3.0
            )

            if params:
                _LOGGER.info("Properties received for %s:", self.test_light.device_id)
                for prop_name, prop_data in params.items():
                    if isinstance(prop_data, dict) and "value" in prop_data:
                        _LOGGER.info("  - %s: %s", prop_name, prop_data["value"])
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
                self.test_light.device_id, timeout=3.0
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
                self.test_light.device_id, timeout=3.0
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

            color_xy_params = {
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
                self.test_light.device_id, timeout=3.0
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

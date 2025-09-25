#!/usr/bin/env python3
"""SDK test script for connection, device discovery, and disconnect functionality."""

import argparse
import asyncio
import logging
import os
import sys
from typing import cast

from dotenv import load_dotenv

from custom_components.azoula_smart.sdk.device_model import DeviceModelProcessor
from custom_components.azoula_smart.sdk.exceptions import AzoulaSmartHubError
from custom_components.azoula_smart.sdk.hub import AzoulaSmartHub
from custom_components.azoula_smart.sdk.types import DeviceType

logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

_LOGGER = logging.getLogger(__name__)


class AzoulaHubTester:
    """Tester for Azoula Hub SDK connection, device discovery, and disconnect."""

    def __init__(self) -> None:
        """Initialize the tester."""
        self.gateway: AzoulaSmartHub | None = None
        self.is_connected = False
        self.device_processor = DeviceModelProcessor()

    async def test_connection(
        self, host: str, username: str, password: str, gateway_id: str
    ) -> bool:
        """Test direct connection to Azoula Hub."""
        _LOGGER.info("=== Testing Hub Connection ===")
        _LOGGER.info("Host: %s", host)
        _LOGGER.info("Username: %s", username)

        try:
            self.gateway = AzoulaSmartHub(
                host=host,
                username=username,
                password=password,
                gateway_id=gateway_id,
            )

            await self.gateway.connect()
            self.is_connected = True

        except AzoulaSmartHubError:
            _LOGGER.exception("Connection error")
            self.is_connected = False
            return False
        else:
            _LOGGER.info(" Successfully connected to gateway!")
            return True

    async def test_get_all_devices(self) -> bool:
        """Test getting all devices from gateway."""
        if not self.gateway or not self.is_connected:
            _LOGGER.warning("Not connected to any gateway")
            return False

        _LOGGER.info("=== Testing Get All Devices ===")
        try:
            devices = await self.gateway.get_all_devices()
            _LOGGER.info("✓ Device discovery completed")
            _LOGGER.info("Found %d device(s):", len(devices))

            # Track platforms needed
            platform_devices: dict[str, list[dict[str, str]]] = {}

            for i, device in enumerate(devices, 1):
                _LOGGER.info("  Device %d:", i)
                _LOGGER.info("    ID: %s", device["device_id"])
                _LOGGER.info("    Type: %s", device["device_type"])
                _LOGGER.info("    Product: %s", device["product_id"])
                _LOGGER.info("    Online: %s", device["online"])
                _LOGGER.info("    Protocol: %s", device["protocol"])

                # Test device model processing - create properly typed dict
                device_dict: dict[str, str] = {
                    "device_id": device["device_id"],
                    "device_type": device["device_type"],
                    "product_id": device["product_id"],
                    "manufacturer": device["manufacturer"],
                    "version": device["version"],
                    "online": device["online"],
                }

                # Cast to DeviceType for the processor methods

                typed_device = cast("DeviceType", device_dict)

                platform = self.device_processor.get_platform_for_device(typed_device)
                should_create = self.device_processor.should_create_entity(typed_device)
                capabilities = self.device_processor.get_device_capabilities(
                    typed_device
                )

                _LOGGER.info("    → Platform: %s", platform)
                _LOGGER.info("    → Should create entity: %s", should_create)

                if should_create and platform:
                    if platform not in platform_devices:
                        platform_devices[platform] = []
                    platform_devices[platform].append(device_dict)

                    # Show capabilities (excluding device_info)
                    caps = [k for k in capabilities if k != "device_info"]
                    if caps:
                        _LOGGER.info("    → Capabilities: %s", caps)

            # Summary of platforms needed
            if platform_devices:
                _LOGGER.info("=== Device Model Processing Summary ===")
                for platform, devices_list in platform_devices.items():
                    _LOGGER.info(
                        "Platform '%s': %d devices", platform, len(devices_list)
                    )
                    for device_info in devices_list:
                        device_name = (
                            device_info["product_id"]
                            or f"Device {device_info['device_id'][-4:]}"
                        )
                        _LOGGER.info("  - %s", device_name)
                _LOGGER.info(
                    "Total platforms needed: %s", list(platform_devices.keys())
                )
            else:
                _LOGGER.warning("No devices require entity creation")

        except Exception:
            _LOGGER.exception("Get all devices error")
            return False

        return True

    async def test_disconnect(self) -> bool:
        """Test disconnect from gateway."""
        if not self.gateway or not self.is_connected:
            _LOGGER.warning("Not connected to any gateway")
            return True

        _LOGGER.info("=== Testing Hub Disconnect ===")
        try:
            await self.gateway.disconnect()
            self.is_connected = False
        except AzoulaSmartHubError:
            _LOGGER.exception("Disconnect error")
            return False
        else:
            _LOGGER.info(" Disconnected successfully")
            return True


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    # Load .env file
    load_dotenv()

    parser = argparse.ArgumentParser(description="Azoula Hub SDK Connection Test Tool")

    parser.add_argument(
        "--host",
        type=str,
        default=os.getenv("AZOULA_HOST"),
        help="Hub host/IP address (default from AZOULA_HOST env var)",
    )

    parser.add_argument(
        "--username",
        type=str,
        default=os.getenv("AZOULA_USERNAME"),
        help="Hub username (default from AZOULA_USERNAME env var)",
    )

    parser.add_argument(
        "--password",
        type=str,
        default=os.getenv("AZOULA_PASSWORD"),
        help="Hub password (default from AZOULA_PASSWORD env var)",
    )

    parser.add_argument(
        "--gateway-id",
        type=str,
        default=os.getenv("AZOULA_GATEWAY_ID"),
        help="Hub ID (default from AZOULA_GATEWAY_ID env var)",
    )

    args = parser.parse_args()

    # Validate required parameters
    if not args.host:
        parser.error("--host is required (or set AZOULA_HOST env var)")
    if not args.username:
        parser.error("--username is required (or set AZOULA_USERNAME env var)")
    if not args.password:
        parser.error("--password is required (or set AZOULA_PASSWORD env var)")

    return args


async def main() -> bool:
    """Main entry point."""
    args = parse_arguments()

    try:
        tester = AzoulaHubTester()

        # Test connection
        success = await tester.test_connection(
            args.host, args.username, args.password, args.gateway_id
        )

        if not success:
            return False

        # Test device discovery
        success = await tester.test_get_all_devices()
        if not success:
            _LOGGER.error("Device discovery test failed")

        # Test disconnect
        success = await tester.test_disconnect()

    except KeyboardInterrupt:
        _LOGGER.exception("Testing interrupted by user")
        return False
    except Exception:
        _LOGGER.exception("Unexpected error")
        return False

    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)

#!/usr/bin/env python3
"""SDK test script for connection, device discovery, and disconnect functionality."""

import argparse
import asyncio
import logging
import os
import sys

from dotenv import load_dotenv

from custom_components.sunricher.sdk.exceptions import AzoulaSmartHubError
from custom_components.sunricher.sdk.hub import AzoulaSmartHub

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

            for i, device in enumerate(devices, 1):
                _LOGGER.info("  Device %d:", i)
                _LOGGER.info("    ID: %s", device.get("device_id", "N/A"))
                _LOGGER.info("    Type: %s", device.get("device_type", "N/A"))
                _LOGGER.info("    Product: %s", device.get("product_id", "N/A"))
                _LOGGER.info("    Online: %s", device.get("online", "N/A"))
                _LOGGER.info("    Protocol: %s", device.get("protocol", "N/A"))

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

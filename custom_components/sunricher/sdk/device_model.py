"""Device model processor for Azoula Smart devices."""

from __future__ import annotations

import logging
from typing import Any

from .const import DEVICE_CAPABILITIES, DEVICE_TYPE_TO_PLATFORM, DOMAIN
from .types import DeviceType

_LOGGER = logging.getLogger(__name__)


class DeviceModelProcessor:
    """Processor for device models to determine HA entity capabilities."""

    def get_platform_for_device(self, device: DeviceType) -> str | None:
        """Get the Home Assistant platform for a device type."""
        return DEVICE_TYPE_TO_PLATFORM.get(device["device_type"])

    def get_device_capabilities(self, device: DeviceType) -> dict[str, Any]:
        """Get device capabilities based on device type."""
        base_capabilities = DEVICE_CAPABILITIES.get(device["device_type"], {})

        # Add common device info
        capabilities: dict[str, Any] = {
            "device_info": {
                "identifiers": {(DOMAIN, device["device_id"])},
                "name": self.get_device_name(device),
                "manufacturer": device["manufacturer"] or "Unknown",
                "model": device["product_id"] or "Unknown",
                "sw_version": device["version"],
            },
        }

        # Add device-specific capabilities
        capabilities.update(base_capabilities)

        _LOGGER.debug(
            "Device %s (type %s) has %d capabilities",
            device["device_id"],
            device["device_type"],
            len(capabilities) - 1,  # Exclude device_info from count
        )

        return capabilities

    def get_device_name(self, device: DeviceType) -> str:
        """Generate a friendly name for the device."""
        if device["product_id"]:
            return device["product_id"]

        # Fallback to device type description
        type_names = {
            "0100": "ON/OFF Light",
            "0101": "Dimmable Light",
            "0102": "RGB Light",
            "010c": "CCT Light",
            "010d": "RGBCCT Light",
        }

        base_name = type_names.get(
            device["device_type"], f"Device {device['device_type']}"
        )
        return f"{base_name} ({device['device_id'][-4:]})"

    def should_create_entity(self, device: DeviceType) -> bool:
        """Determine if we should create an entity for this device."""
        # Only create entities for known device types that are online
        platform = self.get_platform_for_device(device)
        is_online = device["online"] == "1"

        _LOGGER.debug(
            "Device %s: platform=%s, online=%s, should_create=%s",
            device["device_id"],
            platform,
            device["online"],
            platform is not None and is_online,
        )

        return platform is not None and is_online

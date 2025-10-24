"""Data update coordinator for Azoula Smart devices."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .sdk.device_model import DeviceModelProcessor
from .sdk.exceptions import AzoulaSmartHubError
from .sdk.hub import AzoulaSmartHub
from .sdk.types import DeviceType

_LOGGER = logging.getLogger(__name__)


class AzoulaDataUpdateCoordinator(DataUpdateCoordinator[dict[str, DeviceType]]):
    """Data update coordinator for Azoula Smart devices."""

    def __init__(self, hass: HomeAssistant, hub: AzoulaSmartHub) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )
        self.hub = hub
        self.devices: dict[str, DeviceType] = {}
        self.device_processor = DeviceModelProcessor()

        # Set up device status callbacks
        self.hub.on_device_status = self._handle_device_status_change
        self.hub.on_property_update = self._handle_device_property_update

    async def _async_update_data(self) -> dict[str, DeviceType]:
        try:
            devices = await self.hub.get_all_devices()
            device_dict = {device["device_id"]: device for device in devices}

            _LOGGER.debug(
                "Updated device data: %d devices from gateway",
                len(device_dict),
            )

            # Update local cache
            self.devices = device_dict

        except AzoulaSmartHubError as err:
            _LOGGER.exception("Error updating device data from gateway: %s")
            raise UpdateFailed(f"Error communicating with gateway: {err}") from err
        return device_dict

    def _handle_device_status_change(
        self, device_id: str, status: dict[str, Any]
    ) -> None:
        """Handle device status changes from MQTT."""
        if device_id in self.devices:
            _LOGGER.debug(
                "Device %s status change: %s",
                device_id,
                status,
            )

            # Update device online status in cache
            if "online" in status:
                # Create a new device dict with updated online status
                updated_device = DeviceType(
                    device_id=self.devices[device_id]["device_id"],
                    profile=self.devices[device_id]["profile"],
                    device_type=self.devices[device_id]["device_type"],
                    product_id=self.devices[device_id]["product_id"],
                    version=self.devices[device_id]["version"],
                    device_status=self.devices[device_id]["device_status"],
                    online="1" if status["online"] else "0",
                    protocol=self.devices[device_id]["protocol"],
                    manufacturer=self.devices[device_id]["manufacturer"],
                    manufacturer_code=self.devices[device_id]["manufacturer_code"],
                    image_type=self.devices[device_id]["image_type"],
                    household_id=self.devices[device_id]["household_id"],
                    is_added=self.devices[device_id]["is_added"],
                )
                self.devices[device_id] = updated_device

                # Trigger coordinator update
                self.async_set_updated_data(self.devices)

    def _handle_device_property_update(
        self, device_id: str, properties: dict[str, Any]
    ) -> None:
        """Handle device property updates from MQTT."""
        if device_id in self.devices:
            _LOGGER.debug(
                "Device %s property update: %s",
                device_id,
                properties,
            )

            # For property updates, we might want to store additional state
            # For now, just trigger a coordinator update
            self.async_set_updated_data(self.devices)

    def get_device(self, device_id: str) -> DeviceType | None:
        """Get device by ID."""
        return self.devices.get(device_id)

    def get_devices_by_platform(self, platform: str) -> list[DeviceType]:
        """Get all devices for a specific platform."""
        return [
            device
            for device in self.devices.values()
            if self.device_processor.get_platform_for_device(device) == platform
        ]

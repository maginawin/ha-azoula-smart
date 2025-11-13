"""Platform for button integration."""

from __future__ import annotations

import logging

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .sdk.device import AzoulaDevice
from .sdk.gateway import AzoulaGateway
from .types import AzoulaSmartConfigEntry

_LOGGER = logging.getLogger(__name__)

IDENTIFY_BUTTON_DESCRIPTION = ButtonEntityDescription(
    key="identify",
    device_class=ButtonDeviceClass.IDENTIFY,
    entity_category=EntityCategory.CONFIG,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AzoulaSmartConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Azoula Smart buttons from a config entry."""
    async_add_entities(
        [
            AzoulaIdentifyButton(device, entry.runtime_data.gateway)
            for device in entry.runtime_data.devices
            if device.has_identify_support()
        ]
    )


class AzoulaIdentifyButton(ButtonEntity):
    """Representation of an Azoula Smart identify button."""

    _attr_has_entity_name = True
    entity_description = IDENTIFY_BUTTON_DESCRIPTION

    def __init__(self, device: AzoulaDevice, gateway: AzoulaGateway) -> None:
        """Initialize the button entity."""
        self._device = device
        self._gateway = gateway
        self._attr_unique_id = f"{device.device_id}-identify"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device.device_id)},
            "name": device.name,
            "manufacturer": device.manufacturer,
            "model": device.product_id,
            "via_device": (DOMAIN, gateway.gateway_id),
        }

    async def async_press(self) -> None:
        """Press the button to identify the device."""
        await self._gateway.identify_device(self._device.device_id)
        _LOGGER.info("Identified device %s", self._device.device_id)

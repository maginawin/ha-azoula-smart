"""Platform for switch integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .sdk.const import CallbackEventType
from .sdk.device import AzoulaDevice
from .sdk.gateway import AzoulaGateway
from .sdk.types import PropertyParams
from .types import AzoulaSmartConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AzoulaSmartConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Azoula Smart switch entities from a config entry."""
    entities: list[SwitchEntity] = []

    for device in entry.runtime_data.devices:
        gateway = entry.runtime_data.gateway

        # Occupancy LED status switch
        if device.has_property("OccupancyLEDStatus"):
            entities.append(AzoulaOccupancyLEDSwitch(device, gateway))

    async_add_entities(entities)


class AzoulaOccupancyLEDSwitch(SwitchEntity):
    """Switch entity for occupancy sensor LED status."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_is_on: bool | None = None

    def __init__(self, device: AzoulaDevice, gateway: AzoulaGateway) -> None:
        """Initialize the switch entity."""
        self._device = device
        self._gateway = gateway
        self._attr_name = "LED Indicator"
        self._attr_unique_id = f"{device.device_id}-occupancy-led"
        self._attr_available = device.online
        self._attr_icon = "mdi:led-on"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device.device_id)},
            "name": device.name,
            "manufacturer": device.manufacturer,
            "model": device.product_id,
            "via_device": (DOMAIN, gateway.gateway_id),
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the LED indicator."""
        _LOGGER.debug(
            "Turning on LED indicator for device %s",
            self._device.device_id,
        )

        await self._gateway.set_device_properties(
            self._device.device_id,
            {"OccupancyLEDStatus": 1},
        )

        # Update local state
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the LED indicator."""
        _LOGGER.debug(
            "Turning off LED indicator for device %s",
            self._device.device_id,
        )

        await self._gateway.set_device_properties(
            self._device.device_id,
            {"OccupancyLEDStatus": 0},
        )

        # Update local state
        self._attr_is_on = False
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Handle entity addition to Home Assistant."""
        self.async_on_remove(
            self._gateway.register_listener(
                CallbackEventType.PROPERTY_UPDATE, self._handle_device_update
            )
        )

        self.async_on_remove(
            self._gateway.register_listener(
                CallbackEventType.ONLINE_STATUS, self._handle_availability
            )
        )

        # Request initial property value
        await self._gateway.get_device_properties(
            self._device.device_id,
            ["OccupancyLEDStatus"],
        )

        _LOGGER.debug(
            "Requested initial OccupancyLEDStatus property for device %s",
            self._device.device_id,
        )

    @callback
    def _handle_device_update(self, dev_id: str, status: PropertyParams) -> None:
        """Handle device property update."""
        if dev_id != self._device.device_id:
            return

        if "OccupancyLEDStatus" in status:
            value = status["OccupancyLEDStatus"]["value"]
            self._attr_is_on = value == 1
            self.schedule_update_ha_state()

    @callback
    def _handle_availability(self, dev_id: str, available: bool) -> None:
        """Handle device availability update."""
        if dev_id not in (self._device.device_id, self._gateway.gateway_id):
            return

        self._attr_available = available
        self.schedule_update_ha_state()

"""Platform for binary sensor integration."""

from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
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
    """Set up Azoula Smart binary sensors from a config entry."""
    entities: list[AzoulaOccupancySensor] = []

    for device in entry.runtime_data.devices:
        # Check which binary sensor capabilities this device has
        if device.has_property("OccupancyState"):
            entities.append(AzoulaOccupancySensor(device, entry.runtime_data.gateway))

        # Future binary sensor types can be added here
        # if device.has_property("MotionSensorIntrusionIndication"):
        #     entities.append(AzoulaMotionSensor(device, gateway))

    if entities:
        async_add_entities(entities)


class AzoulaOccupancySensor(BinarySensorEntity):
    """Representation of an Azoula Smart occupancy sensor."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY
    _attr_is_on: bool | None = None

    def __init__(self, device: AzoulaDevice, gateway: AzoulaGateway) -> None:
        """Initialize the binary sensor entity."""
        self._device = device
        self._gateway = gateway
        self._attr_name = "Occupancy"
        self._attr_unique_id = f"{device.device_id}-occupancy"
        self._attr_available = device.online
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device.device_id)},
            "name": device.name,
            "manufacturer": device.manufacturer,
            "model": device.product_id,
            "via_device": (DOMAIN, gateway.gateway_id),
        }

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

        await self._gateway.get_device_properties(
            self._device.device_id,
            ["OccupancyState"],
        )

        _LOGGER.debug(
            "Requested initial properties for occupancy sensor %s",
            self._device.device_id,
        )

    @callback
    def _handle_device_update(self, dev_id: str, status: PropertyParams) -> None:
        if dev_id != self._device.device_id:
            return

        if "OccupancyState" in status:
            self._attr_is_on = status["OccupancyState"]["value"] == 1

        self.schedule_update_ha_state()

    @callback
    def _handle_availability(self, dev_id: str, available: bool) -> None:
        if dev_id not in (self._device.device_id, self._gateway.gateway_id):
            return

        self._attr_available = available
        self.schedule_update_ha_state()

"""Platform for sensor integration."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import LIGHT_LUX
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
    """Set up Azoula Smart sensors from a config entry."""
    entities = []

    for device in entry.runtime_data.devices:
        # Check which sensor capabilities this device has
        if device.has_property("IllumMeasuredValue"):
            entities.append(AzoulaIlluminanceSensor(device, entry.runtime_data.gateway))

        # Future sensor types can be added here
        # if device.has_property("Temperature"):
        #     entities.append(AzoulaTemperatureSensor(device, gateway))
        # if device.has_property("Humidity"):
        #     entities.append(AzoulaHumiditySensor(device, gateway))

    if entities:
        async_add_entities(entities)


class AzoulaIlluminanceSensor(SensorEntity):
    """Representation of an Azoula Smart illuminance sensor."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.ILLUMINANCE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = LIGHT_LUX

    def __init__(self, device: AzoulaDevice, gateway: AzoulaGateway) -> None:
        """Initialize the sensor entity."""
        self._device = device
        self._gateway = gateway
        self._attr_name = "Illuminance"
        self._attr_unique_id = f"{device.device_id}-illuminance"
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
            ["IllumMeasuredValue"],
        )

        _LOGGER.debug(
            "Requested initial properties for illuminance sensor %s",
            self._device.device_id,
        )

    @callback
    def _handle_device_update(self, dev_id: str, status: PropertyParams) -> None:
        if dev_id != self._device.device_id:
            return

        if "IllumMeasuredValue" in status:
            self._attr_native_value = status["IllumMeasuredValue"]["value"]

        self.schedule_update_ha_state()

    @callback
    def _handle_availability(self, dev_id: str, available: bool) -> None:
        if dev_id not in (self._device.device_id, self._gateway.gateway_id):
            return

        self._attr_available = available
        self.schedule_update_ha_state()

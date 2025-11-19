"""Platform for sensor integration."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import LIGHT_LUX, EntityCategory, UnitOfEnergy, UnitOfPower
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
    entities: list[SensorEntity] = []

    for device in entry.runtime_data.devices:
        gateway = entry.runtime_data.gateway

        # Illuminance sensor
        if device.has_property("IllumMeasuredValue"):
            entities.append(AzoulaIlluminanceSensor(device, gateway))

        # Energy monitoring sensors
        if device.has_property("CurrentSummationDelivered"):
            entities.append(AzoulaEnergySensor(device, gateway))

        if device.has_property("ActivePower_User"):
            entities.append(AzoulaPowerSensor(device, gateway))

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


class AzoulaEnergySensor(SensorEntity):
    """Representation of an Azoula Smart energy consumption sensor."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

    def __init__(self, device: AzoulaDevice, gateway: AzoulaGateway) -> None:
        """Initialize the energy sensor entity."""
        self._device = device
        self._gateway = gateway
        self._attr_name = "Energy"
        self._attr_unique_id = f"{device.device_id}-energy"
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
            ["CurrentSummationDelivered"],
        )

        _LOGGER.debug(
            "Requested initial properties for energy sensor %s",
            self._device.device_id,
        )

    @callback
    def _handle_device_update(self, dev_id: str, status: PropertyParams) -> None:
        """Handle device property update."""
        if dev_id != self._device.device_id:
            return

        if "CurrentSummationDelivered" in status:
            self._attr_native_value = status["CurrentSummationDelivered"]["value"]

        self.schedule_update_ha_state()

    @callback
    def _handle_availability(self, dev_id: str, available: bool) -> None:
        """Handle device availability update."""
        if dev_id not in (self._device.device_id, self._gateway.gateway_id):
            return

        self._attr_available = available
        self.schedule_update_ha_state()


class AzoulaPowerSensor(SensorEntity):
    """Representation of an Azoula Smart power consumption sensor."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT

    def __init__(self, device: AzoulaDevice, gateway: AzoulaGateway) -> None:
        """Initialize the power sensor entity."""
        self._device = device
        self._gateway = gateway
        self._attr_name = "Power"
        self._attr_unique_id = f"{device.device_id}-power"
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
            ["ActivePower_User"],
        )

        _LOGGER.debug(
            "Requested initial properties for power sensor %s",
            self._device.device_id,
        )

    @callback
    def _handle_device_update(self, dev_id: str, status: PropertyParams) -> None:
        """Handle device property update."""
        if dev_id != self._device.device_id:
            return

        if "ActivePower_User" in status:
            self._attr_native_value = status["ActivePower_User"]["value"]

        self.schedule_update_ha_state()

    @callback
    def _handle_availability(self, dev_id: str, available: bool) -> None:
        """Handle device availability update."""
        if dev_id not in (self._device.device_id, self._gateway.gateway_id):
            return

        self._attr_available = available
        self.schedule_update_ha_state()

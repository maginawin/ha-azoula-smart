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
from .sdk.gateway import AzoulaGateway
from .sdk.illuminance_sensor import IlluminanceSensor
from .sdk.types import PropertyParams
from .types import AzoulaSmartConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AzoulaSmartConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Azoula Smart sensors from a config entry."""

    async_add_entities(
        [
            AzoulaIlluminanceSensor(sensor, entry.runtime_data.gateway)
            for sensor in entry.runtime_data.illuminance_sensors
        ]
    )


class AzoulaIlluminanceSensor(SensorEntity):
    """Representation of an Azoula Smart illuminance sensor."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.ILLUMINANCE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = LIGHT_LUX

    def __init__(self, sensor: IlluminanceSensor, gateway: AzoulaGateway) -> None:
        """Initialize the sensor entity."""
        self._sensor = sensor
        self._gateway = gateway
        self._attr_name = "Illuminance"
        self._attr_unique_id = sensor.unique_id
        self._attr_available = sensor.online
        self._attr_device_info = {
            "identifiers": {(DOMAIN, sensor.device_id)},
            "name": sensor.name,
            "manufacturer": sensor.manufacturer,
            "model": sensor.product_id,
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
            self._sensor.device_id,
            ["IllumMeasuredValue"],
        )

        _LOGGER.debug(
            "Requested initial properties for illuminance sensor %s",
            self._sensor.device_id,
        )

    @callback
    def _handle_device_update(self, dev_id: str, status: PropertyParams) -> None:
        if dev_id != self._attr_unique_id:
            return

        if "IllumMeasuredValue" in status:
            self._attr_native_value = status["IllumMeasuredValue"]["value"]

        self.schedule_update_ha_state()

    @callback
    def _handle_availability(self, dev_id: str, available: bool) -> None:
        if dev_id not in (self._sensor.device_id, self._gateway.gateway_id):
            return

        self._attr_available = available
        self.schedule_update_ha_state()

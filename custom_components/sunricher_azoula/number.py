"""Platform for number integration."""

from __future__ import annotations

import logging

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .sdk.const import CallbackEventType
from .sdk.device import AzoulaDevice
from .sdk.gateway import AzoulaGateway
from .sdk.types import PropertyParams
from .types import AzoulaSmartConfigEntry

_LOGGER = logging.getLogger(__name__)

# Service identifier for property setting
SERVICE_PROPERTY_SET = "set"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AzoulaSmartConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Azoula Smart number entities from a config entry."""
    entities: list[NumberEntity] = []

    for device in entry.runtime_data.devices:
        gateway = entry.runtime_data.gateway

        # MinLevel entities
        if device.has_property("MinLevelSet"):
            entities.append(AzoulaMinLevelNumber(device, gateway, "MinLevelSet"))
        elif device.has_property("LevelControlMinLevel"):
            entities.append(
                AzoulaMinLevelNumber(device, gateway, "LevelControlMinLevel")
            )

        # MaxLevel entities
        if device.has_property("LevelControlMaxLevel"):
            entities.append(AzoulaMaxLevelNumber(device, gateway))

        # Transition time entities
        if device.has_property("OnOffTransitionTime"):
            entities.append(
                AzoulaTransitionTimeNumber(
                    device, gateway, "OnOffTransitionTime", "On/Off Transition Time"
                )
            )
        if device.has_property("OnTransitionTime"):
            entities.append(
                AzoulaTransitionTimeNumber(
                    device, gateway, "OnTransitionTime", "On Transition Time"
                )
            )
        if device.has_property("OffTransitionTime"):
            entities.append(
                AzoulaTransitionTimeNumber(
                    device, gateway, "OffTransitionTime", "Off Transition Time"
                )
            )

        # Sensor configuration entities
        if device.has_property("IlluminanceThreshold"):
            entities.append(AzoulaIlluminanceThresholdNumber(device, gateway))
        if device.has_property("OccupancyDetectionArea"):
            entities.append(AzoulaOccupancyDetectionAreaNumber(device, gateway))

    async_add_entities(entities)


class AzoulaNumberEntity(NumberEntity):
    """Base class for Azoula number entities."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_value: float | None = None
    _property_identifier: str

    def __init__(
        self,
        device: AzoulaDevice,
        gateway: AzoulaGateway,
        property_identifier: str,
    ) -> None:
        """Initialize the number entity."""
        self._device = device
        self._gateway = gateway
        self._property_identifier = property_identifier
        self._attr_available = device.online
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device.device_id)},
            "name": device.name,
            "manufacturer": device.manufacturer,
            "model": device.product_id,
            "via_device": (DOMAIN, gateway.gateway_id),
        }

    async def async_set_native_value(self, value: float) -> None:
        """Set the value."""
        int_value = int(value)
        _LOGGER.debug(
            "Setting %s to %s for device %s",
            self._property_identifier,
            int_value,
            self._device.device_id,
        )

        await self._gateway.invoke_service(
            self._device.device_id,
            SERVICE_PROPERTY_SET,
            {self._property_identifier: int_value},
        )

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
            [self._property_identifier],
        )

        _LOGGER.debug(
            "Requested initial property %s for device %s",
            self._property_identifier,
            self._device.device_id,
        )

    @callback
    def _handle_device_update(self, dev_id: str, status: PropertyParams) -> None:
        """Handle device property update.

        Subclasses should override this method to handle specific properties.
        """
        # Base implementation does nothing - subclasses must override
        _ = dev_id
        _ = status

    @callback
    def _handle_availability(self, dev_id: str, available: bool) -> None:
        """Handle device availability update."""
        if dev_id not in (self._device.device_id, self._gateway.gateway_id):
            return

        self._attr_available = available
        self.schedule_update_ha_state()


class AzoulaMinLevelNumber(AzoulaNumberEntity):
    """Number entity for minimum brightness level setting."""

    def __init__(
        self,
        device: AzoulaDevice,
        gateway: AzoulaGateway,
        property_identifier: str,
    ) -> None:
        """Initialize the min level number entity."""
        super().__init__(device, gateway, property_identifier)
        self._attr_name = "Minimum Brightness"
        self._attr_unique_id = f"{device.device_id}-min-level"
        self._attr_native_min_value = 0
        self._attr_native_max_value = 254
        self._attr_native_step = 1
        self._attr_mode = NumberMode.SLIDER
        self._attr_icon = "mdi:brightness-percent"

    @callback
    def _handle_device_update(self, dev_id: str, status: PropertyParams) -> None:
        """Handle device property update."""
        if dev_id != self._device.device_id:
            return

        # Check for MinLevelSet or LevelControlMinLevel based on property_identifier
        if self._property_identifier == "MinLevelSet" and "MinLevelSet" in status:
            value = status["MinLevelSet"]["value"]
            self._attr_native_value = float(value)
            self.schedule_update_ha_state()
        elif (
            self._property_identifier == "LevelControlMinLevel"
            and "LevelControlMinLevel" in status
        ):
            value = status["LevelControlMinLevel"]["value"]
            self._attr_native_value = float(value)
            self.schedule_update_ha_state()


class AzoulaMaxLevelNumber(AzoulaNumberEntity):
    """Number entity for maximum brightness level setting."""

    def __init__(self, device: AzoulaDevice, gateway: AzoulaGateway) -> None:
        """Initialize the max level number entity."""
        super().__init__(device, gateway, "LevelControlMaxLevel")
        self._attr_name = "Maximum Brightness"
        self._attr_unique_id = f"{device.device_id}-max-level"
        self._attr_native_min_value = 0
        self._attr_native_max_value = 254
        self._attr_native_step = 1
        self._attr_mode = NumberMode.SLIDER
        self._attr_icon = "mdi:brightness-percent"

    @callback
    def _handle_device_update(self, dev_id: str, status: PropertyParams) -> None:
        """Handle device property update."""
        if dev_id != self._device.device_id:
            return

        if "LevelControlMaxLevel" in status:
            value = status["LevelControlMaxLevel"]["value"]
            self._attr_native_value = float(value)
            self.schedule_update_ha_state()


class AzoulaTransitionTimeNumber(AzoulaNumberEntity):
    """Number entity for transition time settings.

    Note: TSL stores transition time in 0.1s units, but we display in seconds.
    The conversion is handled in set/update methods.
    """

    def __init__(
        self,
        device: AzoulaDevice,
        gateway: AzoulaGateway,
        property_identifier: str,
        name: str,
    ) -> None:
        """Initialize the transition time number entity."""
        super().__init__(device, gateway, property_identifier)
        self._attr_name = name
        self._attr_unique_id = (
            f"{device.device_id}-{property_identifier.lower().replace('_', '-')}"
        )
        # Display range in seconds (0 to 6553.5 seconds)
        self._attr_native_min_value = 0.0
        self._attr_native_max_value = 6553.5
        self._attr_native_step = 0.1
        self._attr_native_unit_of_measurement = UnitOfTime.SECONDS
        self._attr_device_class = NumberDeviceClass.DURATION
        self._attr_mode = NumberMode.BOX
        self._attr_icon = "mdi:timer-outline"

    async def async_set_native_value(self, value: float) -> None:
        """Set the value (convert from seconds to 0.1s units)."""
        # Convert from seconds to 0.1s units for the device
        tenths_value = int(value * 10)
        _LOGGER.debug(
            "Setting %s to %s (%.1f seconds) for device %s",
            self._property_identifier,
            tenths_value,
            value,
            self._device.device_id,
        )

        await self._gateway.invoke_service(
            self._device.device_id,
            SERVICE_PROPERTY_SET,
            {self._property_identifier: tenths_value},
        )
        # Update local state (store in seconds for display)
        self._attr_native_value = value
        self.async_write_ha_state()

    @callback
    def _handle_device_update(self, dev_id: str, status: PropertyParams) -> None:
        """Handle device property update."""
        if dev_id != self._device.device_id:
            return

        # Check each possible transition time property explicitly
        raw_value: float | None = None
        if (
            self._property_identifier == "OnOffTransitionTime"
            and "OnOffTransitionTime" in status
        ):
            raw_value = float(status["OnOffTransitionTime"]["value"])
        elif (
            self._property_identifier == "OnTransitionTime"
            and "OnTransitionTime" in status
        ):
            raw_value = float(status["OnTransitionTime"]["value"])
        elif (
            self._property_identifier == "OffTransitionTime"
            and "OffTransitionTime" in status
        ):
            raw_value = float(status["OffTransitionTime"]["value"])

        if raw_value is not None:
            # Convert from 0.1s units to seconds for display
            self._attr_native_value = raw_value / 10.0
            self.schedule_update_ha_state()


class AzoulaIlluminanceThresholdNumber(AzoulaNumberEntity):
    """Number entity for illuminance threshold setting."""

    def __init__(self, device: AzoulaDevice, gateway: AzoulaGateway) -> None:
        """Initialize the illuminance threshold number entity."""
        super().__init__(device, gateway, "IlluminanceThreshold")
        self._attr_name = "Illuminance Threshold"
        self._attr_unique_id = f"{device.device_id}-illuminance-threshold"
        self._attr_native_min_value = 0
        self._attr_native_max_value = 65535
        self._attr_native_step = 1
        self._attr_native_unit_of_measurement = "lx"
        self._attr_device_class = NumberDeviceClass.ILLUMINANCE
        self._attr_mode = NumberMode.BOX
        self._attr_icon = "mdi:brightness-6"

    @callback
    def _handle_device_update(self, dev_id: str, status: PropertyParams) -> None:
        """Handle device property update."""
        if dev_id != self._device.device_id:
            return

        if "IlluminanceThreshold" in status:
            value = status["IlluminanceThreshold"]["value"]
            self._attr_native_value = float(value)
            self.schedule_update_ha_state()


class AzoulaOccupancyDetectionAreaNumber(AzoulaNumberEntity):
    """Number entity for occupancy detection area setting."""

    def __init__(self, device: AzoulaDevice, gateway: AzoulaGateway) -> None:
        """Initialize the occupancy detection area number entity."""
        super().__init__(device, gateway, "OccupancyDetectionArea")
        self._attr_name = "Detection Area"
        self._attr_unique_id = f"{device.device_id}-occupancy-detection-area"
        self._attr_native_min_value = 0
        self._attr_native_max_value = 100
        self._attr_native_step = 1
        self._attr_native_unit_of_measurement = "%"
        self._attr_mode = NumberMode.SLIDER
        self._attr_icon = "mdi:motion-sensor"

    @callback
    def _handle_device_update(self, dev_id: str, status: PropertyParams) -> None:
        """Handle device property update."""
        if dev_id != self._device.device_id:
            return

        if "OccupancyDetectionArea" in status:
            value = status["OccupancyDetectionArea"]["value"]
            self._attr_native_value = float(value)
            self.schedule_update_ha_state()

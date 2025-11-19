"""Platform for select integration."""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
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

# StartUpOnOff options mapping
STARTUP_ONOFF_OPTIONS = {
    "off": 0,
    "on": 1,
    "toggle": 2,
    "previous": 255,
}

STARTUP_ONOFF_REVERSE = {v: k for k, v in STARTUP_ONOFF_OPTIONS.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AzoulaSmartConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Azoula Smart select entities from a config entry."""
    entities: list[SelectEntity] = []

    for device in entry.runtime_data.devices:
        gateway = entry.runtime_data.gateway

        # StartUpOnOff entity
        if device.has_property("StartUpOnOff"):
            entities.append(AzoulaStartUpOnOffSelect(device, gateway))

    async_add_entities(entities)


class AzoulaStartUpOnOffSelect(SelectEntity):
    """Select entity for power-on behavior setting."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_current_option: str | None = None
    _attr_options = list(STARTUP_ONOFF_OPTIONS.keys())

    def __init__(self, device: AzoulaDevice, gateway: AzoulaGateway) -> None:
        """Initialize the select entity."""
        self._device = device
        self._gateway = gateway
        self._attr_name = "Power-on Behavior"
        self._attr_unique_id = f"{device.device_id}-startup-onoff"
        self._attr_available = device.online
        self._attr_icon = "mdi:power-settings"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device.device_id)},
            "name": device.name,
            "manufacturer": device.manufacturer,
            "model": device.product_id,
            "via_device": (DOMAIN, gateway.gateway_id),
        }

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        if option not in STARTUP_ONOFF_OPTIONS:
            _LOGGER.error("Invalid option %s for StartUpOnOff", option)
            return

        value = STARTUP_ONOFF_OPTIONS[option]
        _LOGGER.debug(
            "Setting StartUpOnOff to %s (%d) for device %s",
            option,
            value,
            self._device.device_id,
        )

        await self._gateway.set_device_properties(
            self._device.device_id,
            {"StartUpOnOff": value},
        )

        # Update local state
        self._attr_current_option = option
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
            ["StartUpOnOff"],
        )

        _LOGGER.debug(
            "Requested initial StartUpOnOff property for device %s",
            self._device.device_id,
        )

    @callback
    def _handle_device_update(self, dev_id: str, status: PropertyParams) -> None:
        """Handle device property update."""
        if dev_id != self._device.device_id:
            return

        if "StartUpOnOff" in status:
            raw_value = status["StartUpOnOff"]["value"]
            value = int(raw_value)
            if value in STARTUP_ONOFF_REVERSE:
                self._attr_current_option = STARTUP_ONOFF_REVERSE[value]
            else:
                _LOGGER.warning(
                    "Unknown StartUpOnOff value %s for device %s",
                    value,
                    self._device.device_id,
                )
                self._attr_current_option = None
            self.schedule_update_ha_state()

    @callback
    def _handle_availability(self, dev_id: str, available: bool) -> None:
        """Handle device availability update."""
        if dev_id not in (self._device.device_id, self._gateway.gateway_id):
            return

        self._attr_available = available
        self.schedule_update_ha_state()

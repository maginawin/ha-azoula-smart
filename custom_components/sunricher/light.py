"""Support for Azoula Smart lights."""

from __future__ import annotations

import logging
from typing import Any

from propcache import cached_property

from homeassistant.components.light import LightEntity
from homeassistant.components.light.const import ColorMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import AzoulaDataUpdateCoordinator
from .sdk.device_model import DeviceModelProcessor
from .sdk.types import DeviceType

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Azoula Smart lights from a config entry."""
    coordinator: AzoulaDataUpdateCoordinator = entry.runtime_data
    device_processor = DeviceModelProcessor()

    # Create light entities for devices that should have them
    entities = [
        AzoulaLight(coordinator, device)
        for device in coordinator.data.values()
        if (
            device_processor.should_create_entity(device)
            and device_processor.get_platform_for_device(device) == "light"
        )
    ]

    if entities:
        _LOGGER.info("Adding %d light entities", len(entities))
        async_add_entities(entities)


class AzoulaLight(CoordinatorEntity[AzoulaDataUpdateCoordinator], LightEntity):  # pyright: ignore[reportIncompatibleVariableOverride]
    """Representation of an Azoula Smart light."""

    def __init__(
        self,
        coordinator: AzoulaDataUpdateCoordinator,
        device: DeviceType,
    ) -> None:
        """Initialize the light."""
        super().__init__(coordinator)
        self._device = device
        self._device_processor = DeviceModelProcessor()
        self._capabilities = self._device_processor.get_device_capabilities(device)

        self._attr_unique_id = device["device_id"]
        self._attr_device_info = self._capabilities["device_info"]
        self._attr_name = self._device_processor.get_device_name(device)

        # Determine supported color modes based on capabilities
        supported_color_modes: set[ColorMode] = set()

        if self._capabilities.get("rgb") and self._capabilities.get("color_temp"):
            supported_color_modes.add(ColorMode.RGB)
            supported_color_modes.add(ColorMode.COLOR_TEMP)
        elif self._capabilities.get("rgb"):
            supported_color_modes.add(ColorMode.RGB)
        elif self._capabilities.get("color_temp"):
            supported_color_modes.add(ColorMode.COLOR_TEMP)
        elif self._capabilities.get("brightness"):
            supported_color_modes.add(ColorMode.BRIGHTNESS)
        else:
            supported_color_modes.add(ColorMode.ONOFF)

        self._attr_supported_color_modes = supported_color_modes

        _LOGGER.debug(
            "Created light %s with color modes: %s",
            self._attr_name,
            supported_color_modes,
        )

    @cached_property
    def is_on(self) -> bool | None:
        """Return True if the light is on."""
        # For now, assume all lights are on (we'll implement real status later)
        return True

    @cached_property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 0..255."""
        if (
            self._attr_supported_color_modes
            and ColorMode.BRIGHTNESS in self._attr_supported_color_modes
        ):
            # For now, return a default brightness (we'll implement real status later)
            return 128
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        _LOGGER.info("Turning on light %s", self._attr_name)
        # TODO: Implement actual light control commands
        # For now, just log the action

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        _LOGGER.info("Turning off light %s", self._attr_name)
        # TODO: Implement actual light control commands
        # For now, just log the action

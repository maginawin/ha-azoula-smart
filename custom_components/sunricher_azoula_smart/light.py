"""Platform for light integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
    LightEntity,
)
from homeassistant.components.light.const import ColorMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .sdk.light import Light
from .types import AzoulaSmartConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AzoulaSmartConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Azoula Smart lights from a config entry."""

    async_add_entities([AzoulaLight(light) for light in entry.runtime_data.lights])


class AzoulaLight(LightEntity):
    """Representation of an Azoula Smart light."""

    _attr_has_entity_name = True
    _attr_is_on: bool | None = None
    _attr_brightness: int | None = None
    _attr_color_mode: ColorMode | str | None = None
    _attr_color_temp_kelvin: int | None = None
    _attr_rgb_color: tuple[int, int, int] | None = None
    _attr_max_color_temp_kelvin = 6500
    _attr_min_color_temp_kelvin = 2700

    def __init__(self, device: Light) -> None:
        """Initialize the light entity."""
        self._device = device
        self._attr_name = "Light"
        self._attr_unique_id = device.unique_id
        self._attr_available = device.online
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device.device_id)},
            "name": device.product_id,
            "manufacturer": "Azoula",
            "model": device.product_id,
            "via_device": (DOMAIN, device.device_id.split("-")[0]),
        }

        self._determine_features()

    def _determine_features(self) -> None:
        """Determine supported color modes based on device type."""
        supported_modes: set[ColorMode] = set()

        if "RGBCCT" in self._device.product_id:
            supported_modes.add(ColorMode.RGB)
            supported_modes.add(ColorMode.COLOR_TEMP)
            self._attr_color_mode = ColorMode.RGB
        elif "CCT" in self._device.product_id:
            supported_modes.add(ColorMode.COLOR_TEMP)
            self._attr_color_mode = ColorMode.COLOR_TEMP
        elif "RGB" in self._device.product_id:
            supported_modes.add(ColorMode.RGB)
            self._attr_color_mode = ColorMode.RGB
        else:
            supported_modes.add(ColorMode.BRIGHTNESS)
            self._attr_color_mode = ColorMode.BRIGHTNESS

        self._attr_supported_color_modes = supported_modes

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        color_temp_kelvin = kwargs.get(ATTR_COLOR_TEMP_KELVIN)
        rgb_color = kwargs.get(ATTR_RGB_COLOR)

        _LOGGER.debug(
            "Turning on light %s: brightness=%s, color_temp=%s, rgb=%s",
            self._device.device_id,
            brightness,
            color_temp_kelvin,
            rgb_color,
        )

        self._attr_is_on = True
        if brightness is not None:
            self._attr_brightness = brightness
        if color_temp_kelvin is not None:
            self._attr_color_temp_kelvin = color_temp_kelvin
            self._attr_color_mode = ColorMode.COLOR_TEMP
        if rgb_color is not None:
            self._attr_rgb_color = rgb_color
            self._attr_color_mode = ColorMode.RGB

        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        _LOGGER.debug("Turning off light %s", self._device.device_id)

        self._attr_is_on = False
        self.async_write_ha_state()

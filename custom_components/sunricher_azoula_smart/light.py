"""Platform for light integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
    ATTR_XY_COLOR,
    LightEntity,
)
from homeassistant.components.light.const import ColorMode
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .sdk.const import (
    SERVICE_COLOR_MOVE_TO_COLOR,
    SERVICE_COLOR_TEMP_MOVE_TO_COLOR_TEMP,
    SERVICE_LEVEL_MOVE_TO_LEVEL_WITH_ONOFF,
    SERVICE_ONOFF_OFF,
    SERVICE_ONOFF_ON,
    CallbackEventType,
)
from .sdk.gateway import AzoulaGateway
from .sdk.light import Light
from .sdk.types import PropertyParams
from .types import AzoulaSmartConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AzoulaSmartConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Azoula Smart lights from a config entry."""

    async_add_entities(
        [
            AzoulaLight(light, entry.runtime_data.gateway)
            for light in entry.runtime_data.lights
        ]
    )


class AzoulaLight(LightEntity):
    """Representation of an Azoula Smart light."""

    _attr_has_entity_name = True
    _attr_is_on: bool | None = None
    _attr_brightness: int | None = None
    _attr_color_mode: ColorMode | str | None = None
    _attr_color_temp_kelvin: int | None = None
    _attr_rgb_color: tuple[int, int, int] | None = None
    _attr_xy_color: tuple[float, float] | None = None
    _attr_max_color_temp_kelvin = 6250
    _attr_min_color_temp_kelvin = 2222

    def __init__(self, light: Light, gateway: AzoulaGateway) -> None:
        """Initialize the light entity."""
        self._light = light
        self._gateway = gateway
        self._attr_name = "Light"
        self._attr_unique_id = light.unique_id
        self._attr_available = light.online
        self._attr_device_info = {
            "identifiers": {(DOMAIN, light.device_id)},
            "name": light.name,
            "manufacturer": light.manufacturer,
            "model": light.product_id,
            "via_device": (DOMAIN, gateway.gateway_id),
        }

        self._determine_features()

    def _determine_features(self) -> None:
        """Determine supported color modes based on device type."""
        supported_modes: set[ColorMode] = set()

        if "RGBCCT" in self._light.product_id:
            supported_modes.add(ColorMode.XY)
            supported_modes.add(ColorMode.COLOR_TEMP)
            self._attr_color_mode = ColorMode.XY
        elif "CCT" in self._light.product_id:
            supported_modes.add(ColorMode.COLOR_TEMP)
            self._attr_color_mode = ColorMode.COLOR_TEMP
        elif "RGB" in self._light.product_id:
            supported_modes.add(ColorMode.XY)
            self._attr_color_mode = ColorMode.XY
        else:
            supported_modes.add(ColorMode.BRIGHTNESS)
            self._attr_color_mode = ColorMode.BRIGHTNESS

        self._attr_supported_color_modes = supported_modes

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        color_temp_kelvin = kwargs.get(ATTR_COLOR_TEMP_KELVIN)
        rgb_color = kwargs.get(ATTR_RGB_COLOR)
        xy_color = kwargs.get(ATTR_XY_COLOR)

        _LOGGER.debug(
            "Turning on light %s: brightness=%s, color_temp=%s, rgb=%s, xy=%s",
            self._light.device_id,
            brightness,
            color_temp_kelvin,
            rgb_color,
            xy_color,
        )

        service_invoked = False

        if color_temp_kelvin is not None:
            color_temp = int(color_temp_kelvin)
            min_temp = self._attr_min_color_temp_kelvin
            max_temp = self._attr_max_color_temp_kelvin

            if min_temp is not None and color_temp < min_temp:
                color_temp = min_temp
            if max_temp is not None and color_temp > max_temp:
                color_temp = max_temp

            params = {
                "ColorTemperature": color_temp,
                "TransitionTime": 10,
            }
            await self._gateway.invoke_service(
                self._light.device_id,
                SERVICE_COLOR_TEMP_MOVE_TO_COLOR_TEMP,
                params,
            )
            service_invoked = True

        if xy_color is not None:
            color_x, color_y = xy_color
            clamped_x = max(0.0, min(0.996, float(color_x)))
            clamped_y = max(0.0, min(0.996, float(color_y)))
            params: dict[str, Any] = {
                "ColorX": round(clamped_x, 3),
                "ColorY": round(clamped_y, 3),
                "TransitionTime": 10,
            }
            await self._gateway.invoke_service(
                self._light.device_id,
                SERVICE_COLOR_MOVE_TO_COLOR,
                params,
            )
            service_invoked = True

        if brightness is not None:
            level = max(0, min(254, int(brightness)))
            params = {
                "Level": int(round(level * 100 / 254)),
                "TransitionTime": 10,
            }

            await self._gateway.invoke_service(
                self._light.device_id,
                SERVICE_LEVEL_MOVE_TO_LEVEL_WITH_ONOFF,
                params,
            )
            service_invoked = True

        if not service_invoked:
            await self._gateway.invoke_service(
                self._light.device_id,
                SERVICE_ONOFF_ON,
            )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        _LOGGER.debug("Turning off light %s", self._light.device_id)

        await self._gateway.invoke_service(
            self._light.device_id,
            SERVICE_ONOFF_OFF,
        )
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

    @callback
    def _handle_device_update(self, dev_id: str, status: PropertyParams) -> None:
        if dev_id != self._attr_unique_id:
            return

        if "OnOff" in status:
            self._attr_is_on = status["OnOff"]["value"] == 1

        if "CurrentLevel" in status:
            self._attr_brightness = int(status["CurrentLevel"]["value"] * 254 / 100)
            self._attr_color_mode = ColorMode.BRIGHTNESS

        if "ColorTemperature" in status:
            self._attr_color_temp_kelvin = int(status["ColorTemperature"]["value"])
            self._attr_color_mode = ColorMode.COLOR_TEMP

        current_x = status.get("CurrentX")
        current_y = status.get("CurrentY")
        if current_x is not None or current_y is not None:
            x_value = float(current_x["value"]) if current_x is not None else None
            y_value = float(current_y["value"]) if current_y is not None else None
            if x_value is not None and y_value is not None:
                self._attr_xy_color = (x_value, y_value)
                self._attr_color_mode = ColorMode.XY

        self.schedule_update_ha_state()

    @callback
    def _handle_availability(self, dev_id: str, available: bool) -> None:
        if dev_id not in (self._light.device_id, self._gateway.gateway_id):
            return

        self._attr_available = available
        self.schedule_update_ha_state()

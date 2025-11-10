"""Platform for light integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
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
    SERVICE_COLOR_MOVE_TO_HUE_AND_SATURATION,
    SERVICE_COLOR_TEMP_MOVE_TO_COLOR_TEMP,
    SERVICE_LEVEL_MOVE_TO_LEVEL_WITH_ONOFF,
    SERVICE_ONOFF_OFF,
    SERVICE_ONOFF_ON,
    CallbackEventType,
)
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
    """Set up Azoula Smart lights from a config entry."""
    entities: list[AzoulaLight] = []

    for device in entry.runtime_data.devices:
        # Check if device has light capabilities
        if device.has_property("OnOff"):
            entities.append(AzoulaLight(device, entry.runtime_data.gateway))

    if entities:
        async_add_entities(entities)


class AzoulaLight(LightEntity):
    """Representation of an Azoula Smart light."""

    _attr_has_entity_name = True
    _attr_is_on: bool | None = None
    _attr_brightness: int | None = None
    _attr_color_mode: ColorMode | str | None = None
    _attr_color_temp_kelvin: int | None = None
    _attr_hs_color: tuple[float, float] | None = None
    _attr_rgb_color: tuple[int, int, int] | None = None
    _attr_xy_color: tuple[float, float] | None = None
    _attr_max_color_temp_kelvin = 6250
    _attr_min_color_temp_kelvin = 2222

    def __init__(self, device: AzoulaDevice, gateway: AzoulaGateway) -> None:
        """Initialize the light entity."""
        self._device = device
        self._gateway = gateway
        self._attr_name = "Light"
        self._attr_unique_id = f"{device.device_id}-light"
        self._attr_available = device.online
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device.device_id)},
            "name": device.name,
            "manufacturer": device.manufacturer,
            "model": device.product_id,
            "via_device": (DOMAIN, gateway.gateway_id),
        }

        self._determine_features()

    def _determine_features(self) -> None:
        """Determine supported color modes based on device TSL properties."""
        supported_modes: set[ColorMode] = set()

        # Check device properties from TSL to determine color modes
        has_color_temp = self._device.has_property("ColorTemperature")
        has_xy = self._device.has_property("CurrentX") and self._device.has_property(
            "CurrentY"
        )
        has_hs = self._device.has_property("CurrentHue") and self._device.has_property(
            "CurrentSaturation"
        )
        has_brightness = self._device.has_property("CurrentLevel")

        if has_hs and has_color_temp:
            supported_modes.add(ColorMode.HS)
            supported_modes.add(ColorMode.COLOR_TEMP)
            self._attr_color_mode = ColorMode.HS
        elif has_xy and has_color_temp:
            supported_modes.add(ColorMode.XY)
            supported_modes.add(ColorMode.COLOR_TEMP)
            self._attr_color_mode = ColorMode.XY
        elif has_hs:
            supported_modes.add(ColorMode.HS)
            self._attr_color_mode = ColorMode.HS
        elif has_color_temp:
            supported_modes.add(ColorMode.COLOR_TEMP)
            self._attr_color_mode = ColorMode.COLOR_TEMP
        elif has_xy:
            supported_modes.add(ColorMode.XY)
            self._attr_color_mode = ColorMode.XY
        elif has_brightness:
            supported_modes.add(ColorMode.BRIGHTNESS)
            self._attr_color_mode = ColorMode.BRIGHTNESS
        else:
            # OnOff only
            supported_modes.add(ColorMode.ONOFF)
            self._attr_color_mode = ColorMode.ONOFF

        self._attr_supported_color_modes = supported_modes

    def _get_required_properties(self) -> list[str]:
        """Get list of properties to fetch based on device capabilities."""
        properties = ["OnOff", "CurrentLevel"]

        if (
            self._attr_supported_color_modes
            and ColorMode.COLOR_TEMP in self._attr_supported_color_modes
        ):
            properties.append("ColorTemperature")

        if (
            self._attr_supported_color_modes
            and ColorMode.HS in self._attr_supported_color_modes
        ):
            properties.extend(["CurrentHue", "CurrentSaturation"])

        if (
            self._attr_supported_color_modes
            and ColorMode.XY in self._attr_supported_color_modes
        ):
            properties.extend(["CurrentX", "CurrentY"])

        return properties

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        color_temp_kelvin = kwargs.get(ATTR_COLOR_TEMP_KELVIN)
        hs_color = kwargs.get(ATTR_HS_COLOR)
        rgb_color = kwargs.get(ATTR_RGB_COLOR)
        xy_color = kwargs.get(ATTR_XY_COLOR)
        params: dict[str, Any] = {}

        _LOGGER.debug(
            "Turning on light %s: brightness=%s, color_temp=%s, hs=%s, rgb=%s, xy=%s",
            self._device.device_id,
            brightness,
            color_temp_kelvin,
            hs_color,
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
                self._device.device_id,
                SERVICE_COLOR_TEMP_MOVE_TO_COLOR_TEMP,
                params,
            )
            service_invoked = True

        if hs_color is not None:
            hue, saturation = hs_color
            clamped_hue = max(0, min(360, int(hue)))
            clamped_saturation = max(0, min(100, int(saturation)))
            params = {
                "Hue": clamped_hue,
                "Saturation": clamped_saturation,
                "TransitionTime": 10,
            }
            await self._gateway.invoke_service(
                self._device.device_id,
                SERVICE_COLOR_MOVE_TO_HUE_AND_SATURATION,
                params,
            )
            service_invoked = True

        if xy_color is not None:
            color_x, color_y = xy_color
            clamped_x = max(0.0, min(0.996, float(color_x)))
            clamped_y = max(0.0, min(0.996, float(color_y)))
            params = {
                "ColorX": round(clamped_x, 3),
                "ColorY": round(clamped_y, 3),
                "TransitionTime": 10,
            }
            await self._gateway.invoke_service(
                self._device.device_id,
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
                self._device.device_id,
                SERVICE_LEVEL_MOVE_TO_LEVEL_WITH_ONOFF,
                params,
            )
            service_invoked = True

        if not service_invoked:
            await self._gateway.invoke_service(
                self._device.device_id,
                SERVICE_ONOFF_ON,
            )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        _LOGGER.debug("Turning off light %s", self._device.device_id)

        await self._gateway.invoke_service(
            self._device.device_id,
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

        properties = self._get_required_properties()
        await self._gateway.get_device_properties(
            self._device.device_id,
            properties,
        )

        _LOGGER.debug(
            "Requested initial properties for light %s: %s",
            self._device.device_id,
            properties,
        )

    @callback
    def _handle_device_update(self, dev_id: str, status: PropertyParams) -> None:
        if dev_id != self._device.device_id:
            return

        if "OnOff" in status:
            self._attr_is_on = status["OnOff"]["value"] == 1

        if "CurrentLevel" in status:
            level = status["CurrentLevel"]["value"]
            self._attr_brightness = int(level * 254 / 100)

        if "ColorTemperature" in status:
            color_temp = status["ColorTemperature"]["value"]
            self._attr_color_temp_kelvin = int(color_temp)
            if (
                self._attr_supported_color_modes
                and ColorMode.COLOR_TEMP in self._attr_supported_color_modes
            ):
                self._attr_color_mode = ColorMode.COLOR_TEMP

        current_hue = status.get("CurrentHue")
        current_saturation = status.get("CurrentSaturation")
        if current_hue is not None and current_saturation is not None:
            self._attr_hs_color = (
                float(current_hue["value"]),
                float(current_saturation["value"]),
            )
            if (
                self._attr_supported_color_modes
                and ColorMode.HS in self._attr_supported_color_modes
            ):
                self._attr_color_mode = ColorMode.HS

        current_x = status.get("CurrentX")
        current_y = status.get("CurrentY")
        if current_x is not None and current_y is not None:
            self._attr_xy_color = (
                float(current_x["value"]),
                float(current_y["value"]),
            )
            if (
                self._attr_supported_color_modes
                and ColorMode.XY in self._attr_supported_color_modes
            ):
                self._attr_color_mode = ColorMode.XY

        self.schedule_update_ha_state()

    @callback
    def _handle_availability(self, dev_id: str, available: bool) -> None:
        if dev_id not in (self._device.device_id, self._gateway.gateway_id):
            return

        self._attr_available = available
        self.schedule_update_ha_state()

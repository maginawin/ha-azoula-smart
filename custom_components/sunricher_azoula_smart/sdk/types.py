"""Type definitions for Azoula Smart SDK."""

from collections.abc import Callable
from typing import TypedDict


class PropertyValue(TypedDict):
    """Property value with metadata from thing.event.property.post."""

    value: int | float  # The actual property value
    time: int  # UTC timestamp in milliseconds
    changeByUser: int  # 1 if changed by user, 0 if automatic


class PropertyParams(TypedDict, total=False):
    """Property update parameters from thing.event.property.post."""

    OnOff: PropertyValue  # 0 = off, 1 = on
    CurrentLevel: PropertyValue  # Brightness level 0-254
    ColorTemperature: PropertyValue  # Color temperature in Kelvin
    CurrentHue: PropertyValue  # Hue angle 0-360 degrees
    CurrentSaturation: PropertyValue  # Saturation level 0-100 percent
    CurrentX: PropertyValue  # CIE 1931 color space X coordinate
    CurrentY: PropertyValue  # CIE 1931 color space Y coordinate


ListenerCallback = Callable[[str, bool], None] | Callable[[str, PropertyParams], None]

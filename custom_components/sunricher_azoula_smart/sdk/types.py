"""Type definitions for Azoula Smart SDK."""

from typing import TypedDict


class PropertyValue(TypedDict, total=False):
    """Property value with metadata from thing.event.property.post."""

    value: int | float  # The actual property value
    time: int  # UTC timestamp in milliseconds
    changeByUser: int  # 1 if changed by user, 0 if automatic


class PropertyParams(TypedDict, total=False):
    """Property update parameters from thing.event.property.post."""

    OnOff: PropertyValue  # 0 = off, 1 = on
    CurrentLevel: PropertyValue  # Brightness level 0-254
    ColorTemperature: PropertyValue  # Color temperature in Kelvin
    ColorX: PropertyValue  # CIE 1931 color space X coordinate
    ColorY: PropertyValue  # CIE 1931 color space Y coordinate

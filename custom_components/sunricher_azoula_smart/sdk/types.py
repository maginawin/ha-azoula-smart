"""Type definitions for Azoula Smart SDK."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypedDict


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
    MotionSensorIntrusionIndication: PropertyValue  # 0 = normal, 1 = alarm
    OccupancyState: PropertyValue  # 0 = unoccupied, 1 = occupied
    IllumMeasuredValue: PropertyValue  # Illuminance value 0.0001-3576000 Lux


ListenerCallback = Callable[[str, bool], None] | Callable[[str, PropertyParams], None]


class TSLDataType(TypedDict, total=False):
    """Data type definition in TSL."""

    type: str  # int, float, double, text, date, bool, enum, struct, array
    specs: dict[str, Any]  # Type-specific specifications


class TSLProperty(TypedDict, total=False):
    """Property definition in TSL."""

    identifier: str  # Property unique identifier
    name: str  # Property name
    accessMode: str  # r (read-only) or rw (read-write)
    required: bool  # Whether this is a required standard property
    dataType: TSLDataType  # Property data type


class TSLEvent(TypedDict, total=False):
    """Event definition in TSL."""

    identifier: str  # Event unique identifier
    name: str  # Event name
    desc: str  # Event description
    type: str  # info, alert, or error
    level: int  # Event level 1-4
    required: bool  # Whether this is a required standard event
    outputData: list[dict[str, Any]]  # Event output parameters
    method: str  # Event method name


class TSLService(TypedDict, total=False):
    """Service definition in TSL."""

    identifier: str  # Service unique identifier
    name: str  # Service name
    desc: str  # Service description
    required: bool  # Whether this is a required standard service
    callType: str  # async or sync
    inputData: list[dict[str, Any]]  # Input parameters
    outputData: list[dict[str, Any]]  # Output parameters


class DeviceTSL(TypedDict, total=False):
    """Device Thing Specification Language (TSL) model."""

    profile: str  # Product profile ID
    deviceType: str  # Device type ID
    properties: list[TSLProperty]  # Property definitions
    events: list[TSLEvent]  # Event definitions
    services: list[TSLService]  # Service definitions

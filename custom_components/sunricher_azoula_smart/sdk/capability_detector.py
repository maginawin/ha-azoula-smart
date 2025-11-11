"""TSL-based capability detection for Azoula devices."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .device import AzoulaDevice


class CapabilityDetector:
    """Detects device capabilities based on TSL properties."""

    @staticmethod
    def get_required_platforms(device: AzoulaDevice) -> set[str]:
        """Get required Home Assistant platforms based on device TSL properties."""
        if not device.tsl:
            return set()

        platforms: set[str] = set()
        properties = device.tsl.get("properties", [])

        for prop in properties:
            identifier = prop.get("identifier", "")

            # Light properties
            if identifier in (
                "OnOff",
                "CurrentLevel",
                "ColorTemperature",
                "CurrentHue",
                "CurrentSaturation",
                "CurrentX",
                "CurrentY",
            ):
                platforms.add("light")

            # Sensor properties
            elif identifier in ("IllumMeasuredValue", "Temperature", "Humidity"):
                platforms.add("sensor")

            # Binary sensor properties
            elif identifier in (
                "OccupancyState",
                "MotionSensorIntrusionIndication",
            ):
                platforms.add("binary_sensor")

        return platforms

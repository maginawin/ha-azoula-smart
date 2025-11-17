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
            if identifier in (
                "IllumMeasuredValue",
                "Temperature",
                "Humidity",
                "CurrentSummationDelivered",
                "ActivePower_User",
            ):
                platforms.add("sensor")

            # Binary sensor properties
            if identifier in (
                "OccupancyState",
                "MotionSensorIntrusionIndication",
            ):
                platforms.add("binary_sensor")

            # Number properties (configuration entities)
            if identifier in (
                "MinLevelSet",
                "LevelControlMinLevel",
                "LevelControlMaxLevel",
                "OnOffTransitionTime",
                "OnTransitionTime",
                "OffTransitionTime",
                "IlluminanceThreshold",
                "OccupancyDetectionArea",
            ):
                platforms.add("number")

            # Select properties
            if identifier == "StartUpOnOff":
                platforms.add("select")

            # Switch properties
            if identifier == "OccupancyLEDStatus":
                platforms.add("switch")

        return platforms

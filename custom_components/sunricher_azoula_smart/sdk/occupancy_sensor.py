"""Occupancy sensor device model for Azoula Smart gateway."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class OccupancySensor:
    """Represents an occupancy sensor device under the Azoula gateway.

    Based on Azoula.md device type table:
    - deviceType 0107: Occupancy Sensor
    - Property: OccupancyState (0=unoccupied, 1=occupied)
    """

    name: str
    device_id: str
    profile: str
    device_type: str
    product_id: str
    online: bool
    protocol: str
    manufacturer: str

    # Device state (updated from thing.event.property.post)
    occupied: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OccupancySensor:
        """Create OccupancySensor instance from protocol response dictionary."""
        return cls(
            name=data["config"]["name"],
            device_id=data["deviceID"],
            profile=data["profile"],
            device_type=data["deviceType"],
            product_id=data["productId"],
            online=data["online"] == "1",
            protocol=data["protocol"],
            manufacturer=data["manufacturer"],
        )

    @property
    def unique_id(self) -> str:
        """Return unique identifier for the device."""
        return self.device_id

    @staticmethod
    def is_occupancy_sensor_device(data: dict[str, Any]) -> bool:
        """Check if device data represents an occupancy sensor device."""
        profile = data.get("profile", "")
        device_type = data.get("deviceType", "")
        return bool(profile == "0104" and device_type == "0107")

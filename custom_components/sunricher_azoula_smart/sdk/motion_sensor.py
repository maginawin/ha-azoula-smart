"""Motion sensor device model for Azoula Smart gateway."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class MotionSensor:
    """Represents a motion sensor device under the Azoula gateway."""

    name: str
    device_id: str
    profile: str
    device_type: str
    product_id: str
    online: bool
    protocol: str
    manufacturer: str

    # Device state (updated from thing.event.property.post)
    motion_detected: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MotionSensor:
        """Create MotionSensor instance from protocol response dictionary."""
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
    def is_motion_sensor_device(data: dict[str, Any]) -> bool:
        """Check if device data represents a motion sensor device."""
        profile = data.get("profile", "")
        device_type = data.get("deviceType", "")
        return bool(profile == "0104" and device_type in ("04e1", "0001"))

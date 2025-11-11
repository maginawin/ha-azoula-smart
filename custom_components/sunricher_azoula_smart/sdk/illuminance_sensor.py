"""Illuminance sensor device model for Azoula Smart gateway."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class IlluminanceSensor:
    """Represents an illuminance sensor device under the Azoula gateway.

    Based on thing model documentation:
    - deviceType 0106: Illuminance Sensor
    - Property: IllumMeasuredValue (0.0001-3576000 Lux)
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
    illuminance: float | None = None  # Lux

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IlluminanceSensor:
        """Create IlluminanceSensor instance from protocol response dictionary."""
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
    def is_illuminance_sensor_device(data: dict[str, Any]) -> bool:
        """Check if device data represents an illuminance sensor device."""
        profile = data.get("profile", "")
        device_type = data.get("deviceType", "")
        return bool(profile == "0104" and device_type == "0106")

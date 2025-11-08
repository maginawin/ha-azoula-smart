"""Light device model for Azoula Smart gateway."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Light:
    """Represents a light device under the Azoula gateway."""

    name: str
    device_id: str
    profile: str
    device_type: str
    product_id: str
    online: bool
    protocol: str
    manufacturer: str

    # Device state (updated from thing.event.property.post)
    is_on: bool = False
    brightness: int | None = None  # 0-254
    color_temp: int | None = None  # Kelvin

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Light:
        """Create Light instance from protocol response dictionary."""
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
    def is_light_device(data: dict[str, Any]) -> bool:
        """Check if device data represents a light device.

        Based on Azoula.md device type table:
        - 0100-0105: Various light types and switches
        - 0106: Light Sensor (NOT a light)
        - 0107: Occupancy Sensor (NOT a light)
        - 0108-010d: Light ballasts and units
        - 01Ex: DALI lights
        """
        profile = data.get("profile", "")
        device_type = data.get("deviceType", "")
        # Lighting devices start with 01, but exclude sensors
        return bool(
            profile == "0104"
            and device_type.startswith("01")
            and device_type not in ("0106", "0107")
        )

"""Light device model for Azoula Smart gateway."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Light:
    """Represents a light device under the Azoula gateway."""

    device_id: str
    profile: str
    device_type: str
    product_id: str
    online: bool
    protocol: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Light:
        """Create Light instance from protocol response dictionary."""
        return cls(
            device_id=data["deviceID"],
            profile=data["profile"],
            device_type=data["deviceType"],
            product_id=data["productId"],
            online=data["online"] == "1",
            protocol=data["protocol"],
        )

    @property
    def unique_id(self) -> str:
        """Return unique identifier for the device."""
        return self.device_id

    @staticmethod
    def is_light_device(data: dict[str, Any]) -> bool:
        """Check if device data represents a light device."""
        profile = data.get("profile", "")
        device_type = data.get("deviceType", "")
        return bool(profile == "0104" and device_type.startswith("01"))

"""Unified device model for Azoula Smart gateway."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .types import DeviceTSL


@dataclass
class AzoulaDevice:
    """Represents a unified device under the Azoula gateway.

    This class serves as a container for device basic information and TSL.
    The TSL (Thing Specification Language) defines what capabilities the device has,
    which determines what Home Assistant entities should be created.
    """

    name: str
    device_id: str
    profile: str
    device_type: str
    product_id: str
    online: bool
    protocol: str
    manufacturer: str

    # TSL loaded asynchronously after device discovery
    tsl: DeviceTSL | None = None

    # Device state properties (updated from thing.event.property.post)
    # These are stored here for convenience but the actual entity state
    # will be managed by individual entity classes
    properties: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AzoulaDevice:
        """Create AzoulaDevice instance from protocol response dictionary.

        Args:
            data: Device data from thing.subdev.getall.reply response

        Returns:
            AzoulaDevice instance with basic information populated
        """
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

    def has_property(self, identifier: str) -> bool:
        """Check if device supports a specific property based on TSL.

        Args:
            identifier: Property identifier to check (e.g., "OnOff", "CurrentLevel")

        Returns:
            True if the property exists in device TSL, False otherwise
        """
        if not self.tsl:
            return False

        properties = self.tsl.get("properties", [])
        return any(prop.get("identifier") == identifier for prop in properties)

    def get_property_spec(self, identifier: str) -> dict[str, Any] | None:
        """Get property specification from TSL.

        Args:
            identifier: Property identifier (e.g., "ColorTemperature")

        Returns:
            Property specification dict or None if not found
        """
        if not self.tsl:
            return None

        properties = self.tsl.get("properties", [])
        for prop in properties:
            if prop.get("identifier") == identifier:
                return prop
        return None

    def update_property(self, identifier: str, value: Any) -> None:
        """Update device property value.

        Args:
            identifier: Property identifier
            value: New property value
        """
        self.properties[identifier] = value

    def get_property_value(self, identifier: str, default: Any = None) -> Any:
        """Get current property value.

        Args:
            identifier: Property identifier
            default: Default value if property not found

        Returns:
            Current property value or default
        """
        return self.properties.get(identifier, default)

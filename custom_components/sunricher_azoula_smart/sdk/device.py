"""Unified device model for Azoula Smart gateway."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .types import DeviceTSL, TSLProperty


@dataclass
class AzoulaDevice:
    """Unified device model under the Azoula gateway.

    The TSL (Thing Specification Language) defines device capabilities
    and determines which Home Assistant entities should be created.
    """

    name: str
    device_id: str
    profile: str
    device_type: str
    product_id: str
    online: bool
    protocol: str
    manufacturer: str
    tsl: DeviceTSL | None = None
    properties: dict[str, Any] = field(default_factory=lambda: {})

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AzoulaDevice:
        """Create AzoulaDevice from protocol response dictionary."""
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
        """Check if device supports a property based on TSL."""
        if not self.tsl:
            return False

        properties: list[TSLProperty] = self.tsl.get("properties", [])
        return any(prop.get("identifier") == identifier for prop in properties)

    def get_property_spec(self, identifier: str) -> TSLProperty | None:
        """Get property specification from TSL."""
        if not self.tsl:
            return None

        properties: list[TSLProperty] = self.tsl.get("properties", [])
        for prop in properties:
            if prop.get("identifier") == identifier:
                return prop
        return None

    def update_property(self, identifier: str, value: Any) -> None:
        """Update device property value."""
        self.properties[identifier] = value

    def get_property_value(self, identifier: str, default: Any = None) -> Any:
        """Get current property value."""
        return self.properties.get(identifier, default)

"""Type definitions for the Azoula Smart Hub integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry

from .sdk.device import AzoulaDevice
from .sdk.gateway import AzoulaGateway


@dataclass
class AzoulaSmartData:
    """Runtime data for the Azoula Smart Hub integration."""

    gateway: AzoulaGateway
    devices: list[AzoulaDevice]


type AzoulaSmartConfigEntry = ConfigEntry[AzoulaSmartData]

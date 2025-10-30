"""Type definitions for the Azoula Smart Hub integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry

from .sdk.gateway import AzoulaGateway
from .sdk.light import Light


@dataclass
class AzoulaSmartData:
    """Runtime data for the Azoula Smart Hub integration."""

    gateway: AzoulaGateway
    lights: list[Light]


type AzoulaSmartConfigEntry = ConfigEntry[AzoulaSmartData]

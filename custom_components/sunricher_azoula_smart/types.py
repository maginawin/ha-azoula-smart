"""Type definitions for the Azoula Smart Hub integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry

from .sdk.gateway import AzoulaGateway
from .sdk.illuminance_sensor import IlluminanceSensor
from .sdk.light import Light
from .sdk.occupancy_sensor import OccupancySensor


@dataclass
class AzoulaSmartData:
    """Runtime data for the Azoula Smart Hub integration."""

    gateway: AzoulaGateway
    lights: list[Light]
    occupancy_sensors: list[OccupancySensor]
    illuminance_sensors: list[IlluminanceSensor]


type AzoulaSmartConfigEntry = ConfigEntry[AzoulaSmartData]

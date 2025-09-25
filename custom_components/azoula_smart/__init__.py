"""The Azoula Smart integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_ID,
    CONF_PASSWORD,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant

from .coordinator import AzoulaDataUpdateCoordinator
from .sdk.device_model import DeviceModelProcessor
from .sdk.hub import AzoulaSmartHub

_LOGGER = logging.getLogger(__name__)

# Supported platforms
PLATFORMS: list[Platform] = []

type AzoulaSmartConfigEntry = ConfigEntry[AzoulaDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: AzoulaSmartConfigEntry) -> bool:
    """Set up Azoula Smart from a config entry."""

    host = entry.data[CONF_HOST]
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    gateway_id = entry.data[CONF_ID]

    # Create hub and coordinator
    hub = AzoulaSmartHub(
        host=host,
        username=username,
        password=password,
        gateway_id=gateway_id,
    )

    await hub.connect()

    # Create coordinator and get initial data
    coordinator = AzoulaDataUpdateCoordinator(hass, hub)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    # Determine needed platforms based on discovered devices
    device_processor = DeviceModelProcessor()
    platforms_needed: set[Platform] = set()

    for device in coordinator.data.values():
        if device_processor.should_create_entity(device):
            platform_name = device_processor.get_platform_for_device(device)
            if platform_name:
                platforms_needed.add(Platform(platform_name))

    _LOGGER.info("Loading platforms: %s", platforms_needed)

    if platforms_needed:
        await hass.config_entries.async_forward_entry_setups(entry, platforms_needed)

    _LOGGER.info("Azoula Smart integration setup completed for %s", host)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: AzoulaSmartConfigEntry
) -> bool:
    """Unload a config entry."""

    # Get coordinator and disconnect from MQTT
    coordinator = entry.runtime_data
    await coordinator.hub.disconnect()

    # Unload all platforms that were loaded
    platforms_to_unload = [
        Platform(platform) for platform in ["light", "sensor", "switch"]
    ]
    return await hass.config_entries.async_unload_platforms(entry, platforms_to_unload)

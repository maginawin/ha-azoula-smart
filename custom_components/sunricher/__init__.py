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

from .sdk.hub import AzoulaSmartHub

_LOGGER = logging.getLogger(__name__)

# Supported platforms
PLATFORMS: list[Platform] = []

type AzoulaSmartConfigEntry = ConfigEntry[AzoulaSmartHub]


async def async_setup_entry(hass: HomeAssistant, entry: AzoulaSmartConfigEntry) -> bool:
    """Set up Azoula Smart from a config entry."""

    host = entry.data[CONF_HOST]
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    gateway_id = entry.data[CONF_ID]

    # Create API instance
    hub = AzoulaSmartHub(
        host=host,
        username=username,
        password=password,
        gateway_id=gateway_id,
    )

    await hub.connect()
    entry.runtime_data = hub
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.info("Azoula Smart integration setup completed for %s", host)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: AzoulaSmartConfigEntry
) -> bool:
    """Unload a config entry."""

    # Disconnect from MQTT
    hub = entry.runtime_data
    await hub.disconnect()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

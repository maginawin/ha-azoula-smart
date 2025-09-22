"""The Azoula Smart integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .api import AzoulaSmartAPI

_LOGGER = logging.getLogger(__name__)

# Supported platforms
PLATFORMS: list[Platform] = [Platform.LIGHT]

type AzoulaSmartConfigEntry = ConfigEntry[AzoulaSmartAPI]


async def async_setup_entry(hass: HomeAssistant, entry: AzoulaSmartConfigEntry) -> bool:
    """Set up Azoula Smart from a config entry."""

    host = entry.data[CONF_HOST]
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    # Create API instance
    api = AzoulaSmartAPI(
        hass=hass,
        host=host,
        username=username,
        password=password,
        gateway_id=entry.unique_id,
    )

    if not await api.async_connect():
        raise ConfigEntryNotReady(
            f"Could not connect to Azoula Smart gateway at {host}"
        )

    entry.runtime_data = api
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.info("Azoula Smart integration setup completed for %s", host)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: AzoulaSmartConfigEntry
) -> bool:
    """Unload a config entry."""

    # Disconnect from MQTT
    api = entry.runtime_data
    await api.async_disconnect()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

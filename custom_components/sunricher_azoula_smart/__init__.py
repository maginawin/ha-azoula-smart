"""The Azoula Smart Hub integration."""

from __future__ import annotations

from homeassistant.const import (
    CONF_HOST,
    CONF_ID,
    CONF_PASSWORD,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .sdk.const import DeviceType
from .sdk.exceptions import AzoulaGatewayError
from .sdk.gateway import AzoulaGateway
from .types import AzoulaSmartConfigEntry, AzoulaSmartData

_PLATFORMS: list[Platform] = [Platform.LIGHT]


async def async_setup_entry(hass: HomeAssistant, entry: AzoulaSmartConfigEntry) -> bool:
    """Set up Azoula Smart Hub from a config entry."""
    gateway = AzoulaGateway(
        entry.data[CONF_HOST],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        entry.data[CONF_ID],
    )

    try:
        await gateway.connect()
    except AzoulaGatewayError as err:
        raise ConfigEntryNotReady(
            f"Failed to connect to gateway {entry.data[CONF_ID]}"
        ) from err

    devices = await gateway.discover_devices()

    entry.runtime_data = AzoulaSmartData(
        gateway=gateway,
        lights=devices[DeviceType.LIGHT],
    )

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: AzoulaSmartConfigEntry
) -> bool:
    """Unload a config entry."""
    await entry.runtime_data.gateway.disconnect()
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)

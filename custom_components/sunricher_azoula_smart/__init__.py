"""The Azoula Smart Hub integration."""

from __future__ import annotations

from collections.abc import Sequence
import logging

from homeassistant.const import (
    CONF_HOST,
    CONF_ID,
    CONF_PASSWORD,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, MANUFACTURER
from .sdk.capability_detector import CapabilityDetector
from .sdk.device import AzoulaDevice
from .sdk.exceptions import AzoulaGatewayError
from .sdk.gateway import AzoulaGateway
from .types import AzoulaSmartConfigEntry, AzoulaSmartData

_LOGGER = logging.getLogger(__name__)


def _remove_missing_devices(
    hass: HomeAssistant,
    entry: AzoulaSmartConfigEntry,
    devices: Sequence[AzoulaDevice],
    gateway_identifier: tuple[str, str],
) -> None:
    """Detach devices that are no longer provided by the gateway."""
    device_registry = dr.async_get(hass)
    known_device_ids = {device.device_id for device in devices}

    for device_entry in dr.async_entries_for_config_entry(
        device_registry, entry.entry_id
    ):
        if gateway_identifier in device_entry.identifiers:
            continue

        domain_device_ids = {
            identifier[1]
            for identifier in device_entry.identifiers
            if identifier[0] == DOMAIN
        }

        if not domain_device_ids:
            continue

        if domain_device_ids.isdisjoint(known_device_ids):
            device_registry.async_update_device(
                device_entry.id,
                remove_config_entry_id=entry.entry_id,
            )


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

    dev_reg = dr.async_get(hass)
    dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, gateway.gateway_id)},
        manufacturer=MANUFACTURER,
        name=gateway.gateway_id,
        serial_number=gateway.gateway_id,
    )

    # Discover devices with TSL loading
    devices = await gateway.discover_devices(load_tsl=True)
    _remove_missing_devices(hass, entry, devices, (DOMAIN, gateway.gateway_id))

    _LOGGER.info(
        "Discovered %d device(s) on gateway %s",
        len(devices),
        gateway.gateway_id,
    )

    # Determine which platforms are needed based on device capabilities
    required_platforms: set[str] = set()
    for device in devices:
        platforms = CapabilityDetector.get_required_platforms(device)
        required_platforms.update(platforms)
        _LOGGER.debug(
            "Device %s (%s) supports platforms: %s",
            device.device_id,
            device.name,
            platforms,
        )

    entry.runtime_data = AzoulaSmartData(
        gateway=gateway,
        devices=devices,
    )

    # Only forward to platforms that are actually needed
    # Map platform strings to Platform enum values
    platform_map = {
        "light": Platform.LIGHT,
        "sensor": Platform.SENSOR,
        "binary_sensor": Platform.BINARY_SENSOR,
    }
    platforms_to_load = [
        platform_map[p] for p in required_platforms if p in platform_map
    ]

    if platforms_to_load:
        await hass.config_entries.async_forward_entry_setups(entry, platforms_to_load)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: AzoulaSmartConfigEntry
) -> bool:
    """Unload a config entry."""
    # Determine which platforms were loaded
    required_platforms: set[str] = set()
    for device in entry.runtime_data.devices:
        platforms = CapabilityDetector.get_required_platforms(device)
        required_platforms.update(platforms)

    # Map platform strings to Platform enum values
    platform_map = {
        "light": Platform.LIGHT,
        "sensor": Platform.SENSOR,
        "binary_sensor": Platform.BINARY_SENSOR,
    }
    platforms_to_unload = [
        platform_map[p] for p in required_platforms if p in platform_map
    ]

    await entry.runtime_data.gateway.disconnect()

    if platforms_to_unload:
        return await hass.config_entries.async_unload_platforms(
            entry, platforms_to_unload
        )

    return True

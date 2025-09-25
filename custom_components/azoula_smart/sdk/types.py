"""Type definitions for Azoula Smart gateway."""

from __future__ import annotations

from typing import TypedDict


class DeviceType(TypedDict):
    """Device type definition based on Azoula Smart protocol."""

    device_id: str
    profile: str
    device_type: str
    product_id: str
    version: str
    device_status: str
    online: str
    protocol: str
    manufacturer: str
    manufacturer_code: int
    image_type: int
    household_id: str
    is_added: str


class DeviceListResponse(TypedDict):
    """Response structure for device list query."""

    id: str
    code: int
    page_count: int
    current_page: int
    data: DeviceListData
    method: str


class DeviceListData(TypedDict):
    """Data section of device list response."""

    parent_device_id: str
    device_list: list[DeviceType]

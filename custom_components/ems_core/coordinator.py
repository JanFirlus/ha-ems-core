"""DataUpdateCoordinator für EMS-Core - pollt alle vier Status-Endpoints."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import EMSApiClient, EMSApiError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class EMSDeviceData:
    """Gerät + zugehöriger Live-Status, nach id zusammengeführt."""

    device: dict[str, Any]
    status: dict[str, Any] | None


@dataclass
class EMSCoreData:
    devices: dict[str, EMSDeviceData] = field(default_factory=dict)
    energyflow: dict[str, Any] = field(default_factory=dict)
    loadmanagement: dict[str, Any] = field(default_factory=dict)


class EMSCoreCoordinator(DataUpdateCoordinator[EMSCoreData]):
    """Pollt Geräte/Status/Energiefluss/Lastmanagement gebündelt."""

    def __init__(self, hass: HomeAssistant, client: EMSApiClient) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=DEFAULT_SCAN_INTERVAL)
        self.client = client

    async def _async_update_data(self) -> EMSCoreData:
        try:
            devices, status_list, energyflow, loadmanagement = await asyncio.gather(
                self.client.get_devices(),
                self.client.get_status(),
                self.client.get_energyflow(),
                self.client.get_loadmanagement(),
            )
        except EMSApiError as exc:
            raise UpdateFailed(str(exc)) from exc

        status_by_id = {s["id"]: s for s in status_list}
        devices_data = {
            d["id"]: EMSDeviceData(device=d, status=status_by_id.get(d["id"])) for d in devices
        }

        return EMSCoreData(devices=devices_data, energyflow=energyflow, loadmanagement=loadmanagement)

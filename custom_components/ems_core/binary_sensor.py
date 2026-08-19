"""Binary-Sensor-Plattform für EMS-Core (Online-Status je Gerät + §14a aktiv)."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EMSCoreCoordinator, EMSDeviceData
from .sensor import device_info_for, hub_device_info


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: EMSCoreCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[BinarySensorEntity] = [EMSLoadManagementActiveSensor(coordinator, entry)]
    for device_id in coordinator.data.devices:
        entities.append(EMSDeviceOnlineSensor(coordinator, entry, device_id))

    async_add_entities(entities)


class EMSDeviceOnlineSensor(CoordinatorEntity[EMSCoreCoordinator], BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator: EMSCoreCoordinator, entry: ConfigEntry, device_id: str) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._device_id = device_id
        self._attr_unique_id = f"{entry.entry_id}_{device_id}_online"

    @property
    def _device_data(self) -> EMSDeviceData | None:
        return self.coordinator.data.devices.get(self._device_id)

    @property
    def name(self) -> str | None:
        data = self._device_data
        return f"{data.device['name']} Online" if data else None

    @property
    def device_info(self) -> DeviceInfo:
        return device_info_for(self._entry, self._device_id, self._device_data)

    @property
    def available(self) -> bool:
        return super().available and self._device_data is not None

    @property
    def is_on(self) -> bool | None:
        data = self._device_data
        return data.status.get("online") if data and data.status else None


class EMSLoadManagementActiveSensor(CoordinatorEntity[EMSCoreCoordinator], BinarySensorEntity):
    _attr_name = "§14a aktiv"

    def __init__(self, coordinator: EMSCoreCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_loadmgmt_active"

    @property
    def device_info(self) -> DeviceInfo:
        return hub_device_info(self._entry)

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.loadmanagement.get("active")

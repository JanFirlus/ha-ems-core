"""Sensor-Plattform für EMS-Core."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, POWER_KEYS
from .coordinator import EMSCoreCoordinator, EMSDeviceData


def extract_power_w(detail: dict[str, Any] | None) -> float | None:
    """Portierung von extractPowerW() (ems-stack/ems-core/app/static/app.js)
    bzw. extract_power_w() (ems-stack/ems-core/app/api/energyflow.py)."""
    if not detail:
        return None
    for key in POWER_KEYS:
        value = detail.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    state = detail.get("state")
    unit = detail.get("unit_of_measurement")
    if isinstance(state, str) and isinstance(unit, str):
        try:
            parsed = float(state)
        except ValueError:
            return None
        unit_l = unit.strip().lower()
        if unit_l == "w":
            return parsed
        if unit_l == "kw":
            return parsed * 1000
    return None


def extract_percent(detail: dict[str, Any] | None) -> float | None:
    if not detail:
        return None
    for key in ("soc_percent", "soc"):
        value = detail.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return None


def extract_state_text(detail: dict[str, Any] | None) -> str | None:
    if not detail:
        return None
    state = detail.get("state")
    if isinstance(state, str) and state.strip():
        return state
    return None


def _format_hours(hours: float) -> str:
    total_minutes = round(hours * 60)
    h, m = divmod(total_minutes, 60)
    if h == 0:
        return f"{m}min"
    return f"{h}h {m}min"


def estimate_battery_time(detail: dict[str, Any] | None) -> str | None:
    """Portierung von estimateBatteryTime() (ems-stack/ems-core/app/static/app.js).
    Die EMS-API liefert dieses Ergebnis nirgends fertig - Berechnung passiert dort
    nur clientseitig im EMS-Dashboard, hier also einmalig in Python nachgebaut."""
    if not detail:
        return None
    soc = detail.get("soc_percent")
    power = detail.get("power_w")
    capacity = detail.get("capacity_kwh")
    if (
        not isinstance(soc, (int, float))
        or not isinstance(power, (int, float))
        or not capacity
        or isinstance(soc, bool)
        or isinstance(power, bool)
    ):
        return None

    min_soc = detail.get("min_soc_percent") or 0
    max_soc = detail.get("max_soc_percent") or 100
    noise_floor_w = 10

    if power > noise_floor_w:
        remaining_kwh = capacity * (max_soc - soc) / 100
        if remaining_kwh <= 0:
            return None
        return f"voll in {_format_hours(remaining_kwh / (power / 1000))}"
    if power < -noise_floor_w:
        remaining_kwh = capacity * (soc - min_soc) / 100
        if remaining_kwh <= 0:
            return None
        return f"leer in {_format_hours(remaining_kwh / (abs(power) / 1000))}"
    return None


def hub_device_info(entry: ConfigEntry) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="EMS Core",
        manufacturer="EMS",
        model="EMS Core",
    )


def device_info_for(entry: ConfigEntry, device_id: str, device_data: EMSDeviceData | None) -> DeviceInfo:
    name = device_data.device["name"] if device_data else device_id
    vendor = device_data.device.get("vendor") if device_data else None
    return DeviceInfo(
        identifiers={(DOMAIN, device_id)},
        name=name,
        manufacturer="EMS Core",
        model=vendor,
        via_device=(DOMAIN, entry.entry_id),
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: EMSCoreCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = []
    for device_id, device_data in coordinator.data.devices.items():
        entities.append(EMSDeviceSensor(coordinator, entry, device_id))
        if device_data.device.get("category") == "battery":
            entities.append(EMSBatteryTimeSensor(coordinator, entry, device_id))

    entities.extend(
        [
            EMSEnergyFlowSensor(coordinator, entry, "pv_production_w", "PV-Erzeugung", SensorDeviceClass.POWER, "W"),
            EMSEnergyFlowSensor(coordinator, entry, "grid_import_w", "Netzbezug", SensorDeviceClass.POWER, "W"),
            EMSEnergyFlowSensor(coordinator, entry, "grid_export_w", "Netzeinspeisung", SensorDeviceClass.POWER, "W"),
            EMSEnergyFlowSensor(coordinator, entry, "house_consumption_w", "Hausverbrauch", SensorDeviceClass.POWER, "W"),
            EMSEnergyFlowSensor(coordinator, entry, "consumer_w", "Verbraucher", SensorDeviceClass.POWER, "W"),
            EMSEnergyFlowSensor(coordinator, entry, "battery_power_w", "Akku-Leistung", SensorDeviceClass.POWER, "W"),
            EMSEnergyFlowSensor(coordinator, entry, "battery_soc_percent", "Akku-SOC", SensorDeviceClass.BATTERY, "%"),
            EMSLoadManagementSensor(coordinator, entry, "limit_w", "§14a Limit"),
            EMSLoadManagementSensor(coordinator, entry, "available_w", "§14a Verfügbar"),
            EMSLoadManagementSensor(coordinator, entry, "baseline_reserve_w", "§14a Grundlast-Reserve"),
        ]
    )

    async_add_entities(entities)


class EMSDeviceSensor(CoordinatorEntity[EMSCoreCoordinator], SensorEntity):
    """Hauptwert-Sensor für ein einzelnes EMS-Gerät (Leistung/SOC/Text, je nachdem
    was sich aus dem Status extrahieren lässt). Alle übrigen Detail-Felder landen
    als extra_state_attributes, damit nichts verloren geht."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: EMSCoreCoordinator, entry: ConfigEntry, device_id: str) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._device_id = device_id
        self._attr_unique_id = f"{entry.entry_id}_{device_id}_value"

    @property
    def _device_data(self) -> EMSDeviceData | None:
        return self.coordinator.data.devices.get(self._device_id)

    @property
    def name(self) -> str | None:
        data = self._device_data
        return data.device["name"] if data else None

    @property
    def device_info(self) -> DeviceInfo:
        return device_info_for(self._entry, self._device_id, self._device_data)

    @property
    def available(self) -> bool:
        return super().available and self._device_data is not None

    @property
    def _detail(self) -> dict[str, Any] | None:
        data = self._device_data
        return data.status.get("detail") if data and data.status else None

    @property
    def native_value(self):
        detail = self._detail
        power = extract_power_w(detail)
        if power is not None:
            return power
        percent = extract_percent(detail)
        if percent is not None:
            return percent
        return extract_state_text(detail)

    @property
    def native_unit_of_measurement(self) -> str | None:
        detail = self._detail
        if extract_power_w(detail) is not None:
            return "W"
        if extract_percent(detail) is not None:
            return "%"
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._device_data
        if not data:
            return {}
        attrs: dict[str, Any] = dict((data.status or {}).get("detail") or {})
        attrs["online"] = data.status.get("online") if data.status else None
        attrs["category"] = data.device.get("category")
        attrs["vendor"] = data.device.get("vendor")
        return attrs


class EMSBatteryTimeSensor(CoordinatorEntity[EMSCoreCoordinator], SensorEntity):
    """Voll/Leer-Schätzung für ein Akku-Gerät (nur category == battery)."""

    _attr_icon = "mdi:battery-clock"

    def __init__(self, coordinator: EMSCoreCoordinator, entry: ConfigEntry, device_id: str) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._device_id = device_id
        self._attr_unique_id = f"{entry.entry_id}_{device_id}_time"

    @property
    def _device_data(self) -> EMSDeviceData | None:
        return self.coordinator.data.devices.get(self._device_id)

    @property
    def name(self) -> str | None:
        data = self._device_data
        return f"{data.device['name']} Voll/Leer" if data else None

    @property
    def device_info(self) -> DeviceInfo:
        return device_info_for(self._entry, self._device_id, self._device_data)

    @property
    def available(self) -> bool:
        return super().available and self._device_data is not None

    @property
    def native_value(self) -> str | None:
        data = self._device_data
        if not data or not data.status:
            return None
        return estimate_battery_time(data.status.get("detail"))


class EMSEnergyFlowSensor(CoordinatorEntity[EMSCoreCoordinator], SensorEntity):
    """Ein Sensor pro Feld aus EnergyFlowStatus, unter dem EMS-Core-Hub-Gerät."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: EMSCoreCoordinator,
        entry: ConfigEntry,
        field_key: str,
        label: str,
        device_class: SensorDeviceClass,
        unit: str,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._field_key = field_key
        self._attr_name = label
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        self._attr_unique_id = f"{entry.entry_id}_energyflow_{field_key}"

    @property
    def device_info(self) -> DeviceInfo:
        return hub_device_info(self._entry)

    @property
    def native_value(self):
        return self.coordinator.data.energyflow.get(self._field_key)


class EMSLoadManagementSensor(CoordinatorEntity[EMSCoreCoordinator], SensorEntity):
    """Ein Sensor pro Zahlen-Feld aus LoadManagementStatus (§14a)."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "W"
    _attr_device_class = SensorDeviceClass.POWER

    def __init__(self, coordinator: EMSCoreCoordinator, entry: ConfigEntry, field_key: str, label: str) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._field_key = field_key
        self._attr_name = label
        self._attr_unique_id = f"{entry.entry_id}_loadmgmt_{field_key}"

    @property
    def device_info(self) -> DeviceInfo:
        return hub_device_info(self._entry)

    @property
    def native_value(self):
        return self.coordinator.data.loadmanagement.get(self._field_key)

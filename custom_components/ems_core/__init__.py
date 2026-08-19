"""EMS-Core-Integration - verbindet Home Assistant mit einer EMS-Core-Instanz.

Reine Monitoring-Integration (lesend): stellt Gerätestatus, Energiefluss und
§14a-Lastmanagement-Status des EMS als HA-Entities bereit. Keine Steuerung aus
HA heraus - siehe README für den aktuellen Umfang.
"""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import EMSApiClient
from .const import CONF_EMAIL, CONF_HOST, CONF_PASSWORD, DOMAIN
from .coordinator import EMSCoreCoordinator

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = async_get_clientsession(hass)
    client = EMSApiClient(
        session,
        entry.data[CONF_HOST],
        entry.data[CONF_EMAIL],
        entry.data[CONF_PASSWORD],
    )
    coordinator = EMSCoreCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unloaded

"""Intégration Home Assistant pour gilet chauffant Bluetooth (appli HEATING VEST)."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_ADDRESS, CONF_SERVICE, DEFAULT_SERVICE
from .coordinator import VestCoordinator

PLATFORMS = [Platform.NUMBER, Platform.SELECT, Platform.SENSOR, Platform.SWITCH]

type VestConfigEntry = ConfigEntry[VestCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: VestConfigEntry) -> bool:
    action = entry.options.get(CONF_SERVICE, entry.data.get(CONF_SERVICE, DEFAULT_SERVICE))
    coordinator = VestCoordinator(hass, entry.data[CONF_ADDRESS], action.strip() or None)
    coordinator.async_start()
    entry.runtime_data = coordinator
    entry.async_on_unload(coordinator.async_stop)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_reload(hass: HomeAssistant, entry: VestConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: VestConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

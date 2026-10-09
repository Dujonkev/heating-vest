"""Intégration Home Assistant pour gilet chauffant Bluetooth (appli HEATING VEST)."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_ADDRESS
from .coordinator import VestCoordinator

PLATFORMS = [Platform.NUMBER, Platform.SELECT, Platform.SENSOR, Platform.SWITCH]

type VestConfigEntry = ConfigEntry[VestCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: VestConfigEntry) -> bool:
    coordinator = VestCoordinator(hass, entry.data[CONF_ADDRESS])
    coordinator.async_start()
    entry.runtime_data = coordinator
    entry.async_on_unload(coordinator.async_stop)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: VestConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

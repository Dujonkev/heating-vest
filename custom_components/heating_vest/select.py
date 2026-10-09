"""Sélecteur de niveau de chauffe."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity

from .const import LEVEL_TEMPS
from .entity import VestEntity


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    async_add_entities([VestLevelSelect(entry.runtime_data, "level")])


class VestLevelSelect(VestEntity, SelectEntity):
    _attr_icon = "mdi:thermometer-lines"
    _attr_options = list(LEVEL_TEMPS)

    @property
    def current_option(self) -> str | None:
        level = str(self.coordinator.state.level)
        return level if level in LEVEL_TEMPS else None

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_set_level(option)

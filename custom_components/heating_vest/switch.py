"""Interrupteur marche/arrêt."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity

from .entity import VestEntity


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    async_add_entities([VestPowerSwitch(entry.runtime_data, "power")])


class VestPowerSwitch(VestEntity, SwitchEntity):
    _attr_icon = "mdi:heat-wave"

    @property
    def is_on(self) -> bool:
        return self.coordinator.state.power

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_turn_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_turn_off()

"""Minuterie (minutes)."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import UnitOfTime

from .entity import VestEntity


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    async_add_entities([VestTimerNumber(entry.runtime_data, "timer")])


class VestTimerNumber(VestEntity, NumberEntity):
    _attr_icon = "mdi:timer-outline"
    _attr_native_min_value = 0
    _attr_native_max_value = 120
    _attr_native_step = 5
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_mode = NumberMode.SLIDER

    @property
    def native_value(self) -> float:
        return round(self.coordinator.state.timer_remaining / 60)

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_timer(int(value))

"""Capteurs : consigne et temps restant."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import UnitOfTemperature, UnitOfTime

from .entity import VestEntity


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    c = entry.runtime_data
    async_add_entities([VestTempSensor(c, "setpoint"), VestRemainingSensor(c, "remaining")])


class VestTempSensor(VestEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    @property
    def native_value(self) -> int | None:
        s = self.coordinator.state
        return s.temperature if s.power else None


class VestRemainingSensor(VestEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_suggested_unit_of_measurement = UnitOfTime.MINUTES

    @property
    def native_value(self) -> int:
        return self.coordinator.state.timer_remaining

"""Capteurs : consigne, temps restant et diagnostics Bluetooth."""
from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfTemperature,
    UnitOfTime,
)

from .entity import VestEntity


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    c = entry.runtime_data
    async_add_entities(
        [
            VestTempSensor(c, "setpoint"),
            VestRemainingSensor(c, "remaining"),
            VestRssiSensor(c, "rssi"),
            VestLastSeenSensor(c, "last_seen"),
        ]
    )


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


class VestRssiSensor(VestEntity, SensorEntity):
    """Force du signal de la dernière annonce reçue."""

    _diagnostic_listener = True
    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> int | None:
        return self.coordinator.rssi


class VestLastSeenSensor(VestEntity, SensorEntity):
    """Heure de la dernière annonce reçue (reste disponible quand le gilet est hors de portée)."""

    _diagnostic_listener = True
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def available(self) -> bool:
        return self.coordinator.last_seen_at is not None

    @property
    def native_value(self) -> datetime | None:
        return self.coordinator.last_seen_at

"""Fixtures : annonces BLE fictives du gilet et émetteur simulé."""
from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import patch

import pytest

from homeassistant.core import HomeAssistant

ADDRESS = "ED:67:3B:5A:CD:C0"


def status_bytes(
    *, power: bool, level: int = 2, temperature: int = 50, timer_s: int = 0
) -> bytes:
    """16 octets d'état, tels que diffusés par le gilet."""
    out = bytearray(bytes.fromhex("eebc35000a") + bytes(11))
    out[8:10] = timer_s.to_bytes(2, "little")
    out[10] = 1 if timer_s else 0
    out[11] = 1 if power else 0
    out[13] = level
    out[14] = temperature
    return bytes(out)


def raw_adv(status: bytes) -> bytes:
    """Annonce brute : nom « ves » + liste complète d'UUID 128 bits."""
    return bytes([0x04, 0x09]) + b"ves" + bytes([0x11, 0x07]) + status


@dataclass
class FakeServiceInfo:
    raw: bytes | None
    rssi: int = -60
    service_uuids: list[str] = field(default_factory=list)
    address: str = ADDRESS
    name: str = "ves"


def adv(**kwargs) -> FakeServiceInfo:
    rssi = kwargs.pop("rssi", -60)
    return FakeServiceInfo(raw=raw_adv(status_bytes(**kwargs)), rssi=rssi)


class FakeTransport:
    """Émetteur simulé : applique (ou non) la commande au gilet virtuel."""

    def __init__(self) -> None:
        self.sent: list[bytes] = []
        self.on_send = None  # callable(payload) appelé après chaque émission

    async def send(self, payload: bytes) -> None:
        self.sent.append(payload)
        if self.on_send:
            self.on_send(payload)

    def close(self) -> None:
        return None


@pytest.fixture
def fake_bluetooth():
    """Remplace l'abonnement Bluetooth de HA ; donne accès au callback d'annonces."""
    registered: dict = {}

    def _register(hass, cb, matcher, mode):
        registered["callback"] = cb
        return lambda: registered.pop("callback", None)

    with (
        patch(
            "custom_components.heating_vest.coordinator.bluetooth.async_register_callback",
            side_effect=_register,
        ),
        patch(
            "custom_components.heating_vest.coordinator.bluetooth.async_last_service_info",
            return_value=None,
        ),
    ):
        yield registered


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Active le chargement de custom_components/."""


@pytest.fixture(autouse=True)
def no_bluetooth_adapters(hass: HomeAssistant) -> None:
    """La dépendance bluetooth_adapters n'a pas de matériel en test : on la marque chargée."""
    hass.config.components.add("bluetooth_adapters")

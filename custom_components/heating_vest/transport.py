"""Envoi des commandes au gilet (annonce BLE diffusée).

Par défaut via une action ESPHome (ESP32 dédié, voir esphome/gilet-chauffant-ble.yaml).
Si aucune action n'est configurée, repli sur l'adaptateur BlueZ local (expérimental).
"""
from __future__ import annotations

import struct
import uuid

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import ADV_DURATION_MS


def build_payload(address: str, value: int, cmd: int, seq: int) -> bytes:
    """Octets little-endian de l'UUID de commande."""
    mac_le = bytes.fromhex(address.replace(":", ""))[::-1]
    return mac_le + struct.pack("<HHHH", value & 0xFFFF, cmd, seq & 0xFFFF, 1) + b"\xef\xbc"


def build_adv_data(payload: bytes) -> bytes:
    """Annonce brute identique à celle de l'appli : nom « TSE » + liste d'UUID 128 bits."""
    return bytes([0x04, 0x09]) + b"TSE" + bytes([0x11, 0x07]) + payload


def payload_to_uuid(payload: bytes) -> str:
    return str(uuid.UUID(bytes=payload[::-1]))


class EsphomeTransport:
    """Demande à un ESP32 sous ESPHome de diffuser l'annonce."""

    def __init__(self, hass: HomeAssistant, action: str) -> None:
        domain, _, service = action.partition(".")
        if not domain or not service:
            raise HomeAssistantError(f"Action ESPHome invalide : {action}")
        self.hass = hass
        self.domain = domain
        self.service = service

    async def send(self, payload: bytes) -> None:
        if not self.hass.services.has_service(self.domain, self.service):
            raise HomeAssistantError(
                f"L'action {self.domain}.{self.service} n'existe pas : l'ESP32 est-il en ligne ?"
            )
        await self.hass.services.async_call(
            self.domain,
            self.service,
            {"data": build_adv_data(payload).hex(), "duration_ms": ADV_DURATION_MS},
            blocking=True,
        )

    def close(self) -> None:
        return None


class BluezTransport:
    """Repli expérimental : émission via l'adaptateur Bluetooth local (BlueZ)."""

    def __init__(self) -> None:
        from .advertiser import VestAdvertiser  # import tardif : dbus uniquement si utilisé

        self._adv = VestAdvertiser()

    async def send(self, payload: bytes) -> None:
        await self._adv.send(payload_to_uuid(payload), duration=ADV_DURATION_MS / 1000)

    def close(self) -> None:
        self._adv.close()

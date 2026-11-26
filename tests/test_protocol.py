"""Tests du protocole : décodage de l'état et construction des commandes."""
from __future__ import annotations

import uuid

from custom_components.heating_vest.const import CMD_POWER, POWER_ON
from custom_components.heating_vest.coordinator import parse_status, state_from_status
from custom_components.heating_vest.transport import (
    build_adv_data,
    build_payload,
    payload_to_uuid,
)

from .conftest import ADDRESS, FakeServiceInfo, raw_adv, status_bytes


def test_decode_status_from_raw_advertisement() -> None:
    info = FakeServiceInfo(raw=raw_adv(status_bytes(power=True, level=3, temperature=60, timer_s=1800)))
    state = state_from_status(parse_status(info))
    assert state.power and state.level == 3 and state.temperature == 60
    assert state.timer_active and state.timer_remaining == 1800


def test_decode_status_from_service_uuids_fallback() -> None:
    status = status_bytes(power=False, level=1, temperature=40)
    info = FakeServiceInfo(
        raw=None,
        service_uuids=["0000fff0-0000-1000-8000-00805f9b34fb", str(uuid.UUID(bytes=status[::-1]))],
    )
    state = state_from_status(parse_status(info))
    assert not state.power and state.level == 1 and not state.timer_active


def test_unrelated_advertisement_is_ignored() -> None:
    assert parse_status(FakeServiceInfo(raw=bytes([0x02, 0x01, 0x06]))) is None


def test_build_command_payload() -> None:
    payload = build_payload(ADDRESS, POWER_ON, CMD_POWER, 0x1234)
    assert payload.hex() == "c0cd5a3b67ed" + "9700" + "0300" + "3412" + "0100" + "efbc"
    adv = build_adv_data(payload)
    assert adv[:7] == bytes([0x04, 0x09]) + b"TSE" + bytes([0x11, 0x07])
    assert len(adv) == 23
    assert uuid.UUID(payload_to_uuid(payload)).bytes == payload[::-1]

"""Tests de bout en bout : entités, disponibilité, commandes."""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from custom_components.heating_vest.const import CMD_POWER, CMD_TEMP, DOMAIN
from custom_components.heating_vest.coordinator import state_from_status

from .conftest import ADDRESS, FakeTransport, adv, status_bytes


@pytest.fixture(autouse=True)
def fast_confirm():
    with patch("custom_components.heating_vest.coordinator.CONFIRM_INTERVAL", 0.01):
        yield


@pytest.fixture
async def setup(hass: HomeAssistant, fake_bluetooth):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Gilet chauffant",
        unique_id=ADDRESS,
        data={"address": ADDRESS, "esphome_action": "esphome.gilet_chauffant_ble_send_adv"},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    coordinator = entry.runtime_data
    transport = FakeTransport()
    coordinator._transport = transport  # noqa: SLF001
    return entry, coordinator, transport, fake_bluetooth["callback"]


def _eid(hass: HomeAssistant, domain: str, key: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(domain, DOMAIN, f"{ADDRESS}_{key}")
    assert entity_id, key
    return entity_id


async def test_state_from_advertisements(hass: HomeAssistant, setup) -> None:
    _, _, _, push = setup
    power = _eid(hass, "switch", "power")
    assert hass.states.get(power).state == STATE_UNAVAILABLE  # rien reçu encore

    push(adv(power=True, level=3, temperature=60, timer_s=1200, rssi=-71), None)
    await hass.async_block_till_done()
    assert hass.states.get(power).state == "on"
    assert hass.states.get(_eid(hass, "select", "level")).state == "3"
    assert hass.states.get(_eid(hass, "sensor", "setpoint")).state == "60"
    assert hass.states.get(_eid(hass, "number", "timer")).state == "20"


async def test_goes_unavailable_without_advertisements(hass: HomeAssistant, setup, freezer) -> None:
    _, coordinator, _, push = setup
    push(adv(power=False), None)
    await hass.async_block_till_done()
    power = _eid(hass, "switch", "power")
    assert hass.states.get(power).state == "off"

    # Le gilet s'éteint : plus aucune annonce depuis 2 min. Avant 0.3.0,
    # l'état restait figé indéfiniment.
    coordinator.last_seen -= 120
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(power).state == STATE_UNAVAILABLE
    # La dernière annonce reste consultable.
    assert hass.states.get(_eid(hass, "sensor", "last_seen")).state != STATE_UNAVAILABLE


async def test_diagnostic_sensors_refresh_periodically(hass: HomeAssistant, setup, freezer) -> None:
    _, _, _, push = setup
    push(adv(power=False, rssi=-60), None)
    await hass.async_block_till_done()
    rssi = _eid(hass, "sensor", "rssi")
    first = hass.states.get(rssi).state

    push(adv(power=False, rssi=-82), None)  # même état : pas d'écriture immédiate
    await hass.async_block_till_done()
    assert hass.states.get(rssi).state == first

    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(rssi).state == "-82"


async def test_turn_on_confirmed(hass: HomeAssistant, setup) -> None:
    _, coordinator, transport, push = setup
    push(adv(power=False), None)
    await hass.async_block_till_done()
    transport.on_send = lambda payload: push(adv(power=True), None)

    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": _eid(hass, "switch", "power")}, blocking=True
    )
    assert len(transport.sent) == 1
    assert int.from_bytes(transport.sent[0][8:10], "little") == CMD_POWER
    assert coordinator.state.power


async def test_unconfirmed_command_raises(hass: HomeAssistant, setup) -> None:
    _, _, transport, push = setup
    push(adv(power=False), None)
    await hass.async_block_till_done()

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": _eid(hass, "switch", "power")}, blocking=True
        )
    assert err.value.translation_key == "not_confirmed"
    assert len(transport.sent) == 3  # trois émissions avant d'abandonner


async def test_out_of_range_raises_without_sending(hass: HomeAssistant, setup) -> None:
    _, coordinator, transport, _ = setup
    with pytest.raises(HomeAssistantError) as err:
        await coordinator.async_turn_on()
    assert err.value.translation_key == "out_of_range"
    assert transport.sent == []


async def test_commands_are_serialized(hass: HomeAssistant, setup) -> None:
    """Allumer puis choisir le niveau 3 tout de suite : les commandes ne se mélangent pas."""
    import asyncio

    _, coordinator, transport, push = setup
    push(adv(power=False, level=1, temperature=40), None)
    await hass.async_block_till_done()
    order: list[int] = []

    def apply(payload: bytes) -> None:
        cmd = int.from_bytes(payload[8:10], "little")
        order.append(cmd)
        current = coordinator.state
        if cmd == CMD_POWER:
            push(adv(power=True, level=current.level, temperature=current.temperature), None)
        elif cmd == CMD_TEMP:
            push(adv(power=True, level=3, temperature=60), None)

    transport.on_send = apply
    await asyncio.gather(coordinator.async_turn_on(), coordinator.async_set_level("3"))
    assert order == [CMD_POWER, CMD_TEMP]
    assert state_from_status(status_bytes(power=True, level=3, temperature=60)) == coordinator.state

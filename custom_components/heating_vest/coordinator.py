"""État et commandes du gilet chauffant."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
import random
import time
import uuid

from homeassistant.components import bluetooth
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .const import (
    CMD_POWER,
    CMD_TEMP,
    CMD_TIMER,
    COMMAND_ATTEMPTS,
    CONFIRM_CHECKS,
    CONFIRM_INTERVAL,
    DIAGNOSTIC_INTERVAL,
    DOMAIN,
    LEVEL_TEMPS,
    POWER_OFF,
    POWER_ON,
    STATUS_PREFIX,
    UNAVAILABLE_AFTER,
)
from .transport import BluezTransport, EsphomeTransport, build_payload

_LOGGER = logging.getLogger(__name__)


@dataclass
class VestState:
    power: bool = False
    level: int = 0
    temperature: int = 0
    timer_active: bool = False
    timer_remaining: int = 0  # secondes


def _status_from_raw(raw: bytes | None) -> bytes | None:
    """Cherche la liste d'UUID 128 bits (type 0x06/0x07) dans l'annonce brute."""
    if not raw:
        return None
    i = 0
    while i + 1 < len(raw):
        length = raw[i]
        if length == 0:
            break
        ad_type = raw[i + 1]
        data = raw[i + 2 : i + 1 + length]
        if ad_type in (0x06, 0x07):
            for j in range(0, len(data) - 15, 16):
                chunk = data[j : j + 16]
                if chunk.startswith(STATUS_PREFIX):
                    return chunk
        i += 1 + length
    return None


def parse_status(service_info: bluetooth.BluetoothServiceInfoBleak) -> bytes | None:
    status = _status_from_raw(getattr(service_info, "raw", None))
    if status is not None:
        return status
    # Repli : HA cumule les UUID, on prend le dernier qui correspond
    for value in reversed(service_info.service_uuids):
        try:
            le = uuid.UUID(value).bytes[::-1]
        except ValueError:
            continue
        if le.startswith(STATUS_PREFIX):
            return le
    return None


def state_from_status(status: bytes) -> VestState:
    """Décode les 16 octets d'état diffusés par le gilet."""
    timer_active = status[10] == 1
    return VestState(
        power=status[11] == 1,
        level=status[13],
        temperature=status[14],
        timer_active=timer_active,
        timer_remaining=int.from_bytes(status[8:10], "little") if timer_active else 0,
    )


class VestCoordinator:
    """Écoute les annonces du gilet et lui envoie des commandes."""

    def __init__(self, hass: HomeAssistant, address: str, action: str | None) -> None:
        self.hass = hass
        self.address = address.upper()
        self.state = VestState()
        self.last_seen: float = 0  # time.monotonic() de la dernière annonce
        self.last_seen_at: datetime | None = None
        self.rssi: int | None = None
        self._was_available = False
        self._seq = random.randint(0x100, 0x7FFF)
        self._transport = EsphomeTransport(hass, action) if action else BluezTransport()
        self._command_lock = asyncio.Lock()
        self._listeners: list[Callable[[], None]] = []
        self._diag_listeners: list[Callable[[], None]] = []
        self._unsubs: list[CALLBACK_TYPE] = []

    @property
    def available(self) -> bool:
        return self.last_seen > 0 and time.monotonic() - self.last_seen < UNAVAILABLE_AFTER

    # -- Cycle de vie ---------------------------------------------------------

    @callback
    def async_start(self) -> None:
        self._unsubs.append(
            bluetooth.async_register_callback(
                self.hass,
                self._async_on_advertisement,
                bluetooth.BluetoothCallbackMatcher(address=self.address, connectable=False),
                bluetooth.BluetoothScanningMode.PASSIVE,
            )
        )
        # Sans annonce, rien ne réveille les entités : on vérifie donc
        # régulièrement la disponibilité (et on rafraîchit les diagnostics).
        self._unsubs.append(
            async_track_time_interval(
                self.hass, self._async_periodic, timedelta(seconds=DIAGNOSTIC_INTERVAL)
            )
        )
        last = bluetooth.async_last_service_info(self.hass, self.address, connectable=False)
        if last is not None:
            self._async_on_advertisement(last, bluetooth.BluetoothChange.ADVERTISEMENT)

    @callback
    def async_stop(self) -> None:
        while self._unsubs:
            self._unsubs.pop()()
        self._transport.close()

    # -- Abonnements des entités ----------------------------------------------

    @callback
    def async_add_listener(
        self, update: Callable[[], None], *, diagnostic: bool = False
    ) -> Callable[[], None]:
        """Entités d'état : notifiées à chaque changement d'état.

        Entités de diagnostic (RSSI, dernière annonce) : notifiées toutes les
        DIAGNOSTIC_INTERVAL secondes, le gilet annonçant plusieurs fois par
        seconde.
        """
        target = self._diag_listeners if diagnostic else self._listeners
        target.append(update)

        def _remove() -> None:
            target.remove(update)

        return _remove

    @callback
    def _notify(self, listeners: list[Callable[[], None]]) -> None:
        for update in list(listeners):
            update()

    @callback
    def _async_periodic(self, _now: datetime | None = None) -> None:
        available = self.available
        if available != self._was_available:
            self._was_available = available
            _LOGGER.debug(
                "Gilet %s %s", self.address, "de nouveau visible" if available else "hors de portée"
            )
            self._notify(self._listeners)
        self._notify(self._diag_listeners)

    @callback
    def _async_on_advertisement(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        status = parse_status(service_info)
        if status is None:
            return
        self.last_seen = time.monotonic()
        self.last_seen_at = dt_util.utcnow()
        self.rssi = getattr(service_info, "rssi", None)
        new_state = state_from_status(status)
        # N'écrit l'état dans HA que s'il a changé (le gilet annonce plusieurs fois par seconde)
        if new_state == self.state and self._was_available:
            return
        self.state = new_state
        self._was_available = True
        self._notify(self._listeners)

    # -- Commandes ------------------------------------------------------------

    async def _send(self, value: int, cmd: int, done: Callable[[VestState], bool]) -> None:
        """Diffuse la commande et la répète tant que le gilet ne l'a pas appliquée.

        Les commandes sont envoyées une par une : sans verrou, les répétitions
        de deux commandes rapprochées (ex. allumer puis niveau 3) se mêlent.
        """
        async with self._command_lock:
            if not self.available:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="out_of_range",
                )
            for attempt in range(1, COMMAND_ATTEMPTS + 1):
                self._seq = (self._seq + 1) & 0xFFFF or 1
                payload = build_payload(self.address, value, cmd, self._seq)
                _LOGGER.debug(
                    "Commande gilet %s (essai %s) : %s", self.address, attempt, payload.hex()
                )
                await self._transport.send(payload)
                for _ in range(CONFIRM_CHECKS):
                    if done(self.state):
                        return
                    await asyncio.sleep(CONFIRM_INTERVAL)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="not_confirmed",
            )

    async def async_turn_on(self) -> None:
        await self._send(POWER_ON, CMD_POWER, lambda s: s.power)

    async def async_turn_off(self) -> None:
        await self._send(POWER_OFF, CMD_POWER, lambda s: not s.power)

    async def async_set_level(self, level: str) -> None:
        await self._send(LEVEL_TEMPS[level], CMD_TEMP, lambda s: s.power and s.level == int(level))

    async def async_set_timer(self, minutes: int) -> None:
        await self._send(int(minutes) * 60, CMD_TIMER, lambda s: s.timer_active == (minutes > 0))

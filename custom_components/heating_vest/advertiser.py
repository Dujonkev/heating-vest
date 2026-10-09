"""Émission d'annonces BLE via BlueZ (D-Bus) pour piloter le gilet.

Le gilet n'accepte pas de connexion : l'appli diffuse un UUID 128 bits
contenant [MAC du gilet][valeur][commande][séquence][01 00][ef bc].
"""
import asyncio
import logging
import struct
import uuid

from dbus_fast import BusType, Message, MessageType, Variant
from dbus_fast.aio import MessageBus
from dbus_fast.service import PropertyAccess, ServiceInterface, dbus_property, method

_LOGGER = logging.getLogger(__name__)

ADV_PATH = "/org/heating_vest/adv{}"


class _Advertisement(ServiceInterface):
    def __init__(self, service_uuid: str) -> None:
        super().__init__("org.bluez.LEAdvertisement1")
        self._uuid = service_uuid

    @method()
    def Release(self) -> None:  # noqa: N802
        return None

    @dbus_property(access=PropertyAccess.READ)
    def Type(self) -> "s":  # noqa: N802,F821
        return "broadcast"

    @dbus_property(access=PropertyAccess.READ)
    def ServiceUUIDs(self) -> "as":  # noqa: N802,F821
        return [self._uuid]

    @dbus_property(access=PropertyAccess.READ)
    def LocalName(self) -> "s":  # noqa: N802,F821
        return "TSE"

    @dbus_property(access=PropertyAccess.READ)
    def MinInterval(self) -> "u":  # noqa: N802,F821
        return 30

    @dbus_property(access=PropertyAccess.READ)
    def MaxInterval(self) -> "u":  # noqa: N802,F821
        return 60


def build_uuid(address: str, value: int, cmd: int, seq: int) -> str:
    """Construit l'UUID de commande (octets little-endian inversés)."""
    mac_le = bytes.fromhex(address.replace(":", ""))[::-1]
    payload = mac_le + struct.pack("<HHHH", value & 0xFFFF, cmd, seq & 0xFFFF, 1) + b"\xef\xbc"
    return str(uuid.UUID(bytes=payload[::-1]))


class VestAdvertiser:
    """Diffuse brièvement une commande via un adaptateur BlueZ local."""

    def __init__(self) -> None:
        self._bus: MessageBus | None = None
        self._lock = asyncio.Lock()
        self._counter = 0

    async def _get_bus(self) -> MessageBus:
        if self._bus is None or not self._bus.connected:
            self._bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
        return self._bus

    async def _adapters(self, bus: MessageBus) -> list[str]:
        reply = await bus.call(
            Message(
                destination="org.bluez",
                path="/",
                interface="org.freedesktop.DBus.ObjectManager",
                member="GetManagedObjects",
            )
        )
        if reply.message_type == MessageType.ERROR:
            raise RuntimeError(f"BlueZ indisponible : {reply.body}")
        return sorted(
            path
            for path, ifaces in reply.body[0].items()
            if "org.bluez.LEAdvertisingManager1" in ifaces
        )

    async def send(self, service_uuid: str, duration: float = 2.5) -> None:
        async with self._lock:
            bus = await self._get_bus()
            adapters = await self._adapters(bus)
            if not adapters:
                raise RuntimeError("Aucun adaptateur Bluetooth local capable d'émettre")
            self._counter += 1
            path = ADV_PATH.format(self._counter)
            adv = _Advertisement(service_uuid)
            bus.export(path, adv)
            registered: list[str] = []
            try:
                for adapter in adapters:
                    reply = await bus.call(
                        Message(
                            destination="org.bluez",
                            path=adapter,
                            interface="org.bluez.LEAdvertisingManager1",
                            member="RegisterAdvertisement",
                            signature="oa{sv}",
                            body=[path, {}],
                        )
                    )
                    if reply.message_type == MessageType.ERROR:
                        _LOGGER.debug("Annonce refusée par %s : %s", adapter, reply.body)
                    else:
                        registered.append(adapter)
                if not registered:
                    raise RuntimeError("Aucun adaptateur n'a accepté l'annonce")
                await asyncio.sleep(duration)
            finally:
                for adapter in registered:
                    await bus.call(
                        Message(
                            destination="org.bluez",
                            path=adapter,
                            interface="org.bluez.LEAdvertisingManager1",
                            member="UnregisterAdvertisement",
                            signature="o",
                            body=[path],
                        )
                    )
                bus.unexport(path, adv)

    def close(self) -> None:
        if self._bus is not None:
            self._bus.disconnect()
            self._bus = None


_ = Variant  # garde l'import disponible pour les options éventuelles

"""Legacy, non-connectable BlueZ advertisement on the configured Linux adapter."""
import asyncio

from dbus_fast import BusType, Variant
from dbus_fast.aio import MessageBus
from dbus_fast.errors import DBusError
from dbus_fast.service import ServiceInterface, dbus_property, method
from dbus_fast.constants import PropertyAccess

from ble.demo_packets import CONTROL


class Advertisement(ServiceInterface):
    def __init__(self, payload):
        super().__init__("org.bluez.LEAdvertisement1")
        self.payload = payload

    @dbus_property(access=PropertyAccess.READ)
    def Type(self) -> "s":
        return "broadcast"

    @dbus_property(access=PropertyAccess.READ)
    def ManufacturerData(self) -> "a{qv}":
        return {CONTROL: Variant("ay", self.payload)}

    @method()
    def Release(self):
        pass


async def transmitter(adapter):
    bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
    adapter_path = "/org/bluez/" + adapter
    node = await bus.introspect("org.bluez", adapter_path)
    manager = bus.get_proxy_object("org.bluez", adapter_path, node).get_interface(
        "org.bluez.LEAdvertisingManager1"
    )
    path = "/org/kinbeacon/DemoAdvertisement"

    async def send(payload, seconds):
        bus.export(path, Advertisement(payload))
        try:
            await manager.call_register_advertisement(path, {})
            try:
                await asyncio.sleep(seconds)
            finally:
                await manager.call_unregister_advertisement(path)
        except DBusError as exc:
            raise RuntimeError(str(exc)) from exc
        finally:
            bus.unexport(path)

    return send

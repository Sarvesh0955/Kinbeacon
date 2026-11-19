import asyncio
import json
import logging
from queue import Empty, Full, Queue
from threading import Thread
from time import monotonic, time
from urllib.request import Request, urlopen

from ble.demo_packets import CONTROL, HEARTBEAT, decode, encode

logger = logging.getLogger("ble.demo")


class DemoRadio:
    def __init__(self, server, adapter, mock):
        self.url = server.rstrip("/") + "/api/v1/demo"
        self.adapter = adapter
        self.mock = mock
        self.events = Queue(maxsize=64)
        self.heard = {}
        self.last_sighting = float("-inf")

    def receive(self, advertisement):
        now = monotonic()
        if advertisement.manufacturer_data.get(0xFFFF) == HEARTBEAT and now - self.last_sighting >= 2:
            self.last_sighting = now
            rssi = advertisement.rssi
            self.enqueue(dict(kind="sighting", rssi=rssi if rssi is not None and -127 <= rssi <= 20 else -100))

        self.heard = {key: expiry for key, expiry in self.heard.items() if expiry > now}
        for company in (0xFFFE, 0xFFFD):
            payload = advertisement.manufacturer_data.get(company, b"")
            packet = decode(company, payload)
            if not packet or packet[0] not in (0, 5) or payload in self.heard:
                continue
            kind, incident_id, _, fields = packet
            event = dict(incident_id=incident_id)
            if kind == 0:
                event["kind"] = "find_request"
            else:
                event.update(kind="uplink", lat=fields[1] / 1e7, lon=fields[2] / 1e7)
            if self.enqueue(event):
                self.heard[payload] = now + 1.5

    def enqueue(self, event):
        try:
            self.events.put_nowait(event)
            return True
        except Full:
            return False

    def request(self, route, payload=None):
        body = json.dumps(payload).encode() if payload is not None else None
        request = Request(self.url + route, data=body, headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=1) as response:
            return json.load(response)

    async def forward_events(self, stop):
        while not stop.is_set():
            try:
                event = self.events.get_nowait()
            except Empty:
                await asyncio.sleep(0.05)
                continue
            try:
                await asyncio.to_thread(self.request, "/anchor/events", event)
            except OSError as exc:
                logger.warning("Demo event delivery failed: %s", exc)
                # A short retry accommodates a transient LAN failure within the search window.
                if not hasattr(exc, "code") or exc.code >= 500:
                    try:
                        await asyncio.to_thread(self.request, "/anchor/events", event)
                    except OSError:
                        pass

    async def send_commands(self, stop, transmit):
        completed = {}
        while not stop.is_set():
            try:
                commands = await asyncio.to_thread(self.request, "/anchor/commands")
                now = time()
                completed = {key: expiry for key, expiry in completed.items() if expiry > now}
                for command in commands:
                    command_id = command["command_id"]
                    expiry = command["expires_at"]
                    if expiry <= time() or stop.is_set():
                        continue
                    if command_id not in completed:
                        incident_id = command["incident_id"]
                        if command["kind"] == "find_target":
                            packet = encode(1, incident_id, 2, 1, 0)
                        elif command["kind"] == "loc_result":
                            packet = encode(
                                4, incident_id, 2, round(command["lat"] * 1e7),
                                round(command["lon"] * 1e7), command["radius_m"],
                                command["landmark_index"],
                            )
                        else:
                            continue
                        await transmit(packet, min(1.0, expiry - time()))
                        completed[command_id] = expiry
                    await asyncio.to_thread(self.request, "/anchor/events", {
                        "kind": "ack", "command_id": command_id,
                    })
            except (OSError, ValueError, RuntimeError) as exc:
                logger.warning("Demo command poll failed: %s", exc)
            await asyncio.sleep(0.25)

    async def run(self, stop):
        async def mock_transmit(payload, seconds):
            logger.info("[MOCK TX] %04x %s", CONTROL, payload.hex())
            await asyncio.sleep(seconds)

        if self.mock:
            transmit = mock_transmit
        else:
            from ble.demo_bluez import transmitter
            transmit = await transmitter(self.adapter)
        await asyncio.gather(self.forward_events(stop), self.send_commands(stop, transmit))

    def start(self, stop):
        def worker():
            try:
                asyncio.run(self.run(stop))
            except Exception:
                logger.exception("Demo anchor radio stopped")

        thread = Thread(target=worker, name="DemoRadio", daemon=True)
        thread.start()
        return thread

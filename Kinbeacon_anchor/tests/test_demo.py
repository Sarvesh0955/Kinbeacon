import asyncio
from pathlib import Path
from threading import Event
from time import time
from types import SimpleNamespace
from urllib.error import URLError

from ble.demo import DemoRadio
from ble.demo_packets import CONTROL, HEARTBEAT, UPLINK, decode, encode

FIXTURES = Path(__file__).resolve().parents[2] / "kimbeacon_app/app/src/test/resources/demo_packets.txt"


def test_shared_frames():
    seen = []
    for line in FIXTURES.read_text().splitlines():
        company, payload = line.split()
        company, payload = int(company, 16), bytes.fromhex(payload)
        kind, incident_id, ttl, fields = decode(company, payload)
        assert incident_id == 0xBEEF
        assert encode(kind, incident_id, ttl, *fields) == payload
        assert decode(company, payload[:-1]) is None
        assert decode(0xFFFF, payload) is None
        if kind in (3, 4, 5):
            assert (120002400, -770001800) == (fields[:2] if kind == 4 else fields[1:3])
        seen.append(kind)
    assert seen == list(range(6))


def test_anchor_forwards_once_per_burst():
    radio = DemoRadio("http://localhost", "hci0", mock=True)
    advertisement = SimpleNamespace(
        manufacturer_data={
            0xFFFF: HEARTBEAT,
            CONTROL: encode(0, 7, 2, 1),
            UPLINK: encode(5, 7, 1, 1, 120002400, 770001800),
        },
        rssi=-65,
    )
    radio.receive(advertisement)
    radio.receive(advertisement)
    assert [radio.events.get_nowait()["kind"] for _ in range(3)] == ["sighting", "find_request", "uplink"]
    assert radio.events.empty()


def test_command_ack_retry_does_not_retransmit():
    radio = DemoRadio("http://localhost", "hci0", mock=True)
    stop = Event()
    command = dict(command_id="x", kind="find_target", incident_id=7, expires_at=time() + 5)
    attempts = []
    transmitted = []

    def request(route, payload=None):
        if route.endswith("commands"):
            return [command]
        attempts.append(payload)
        if len(attempts) == 1:
            raise URLError("Temporary failure")
        stop.set()
        return {"ok": True}

    async def transmit(packet, seconds):
        transmitted.append(packet)
        assert seconds > 0

    radio.request = request
    asyncio.run(asyncio.wait_for(radio.send_commands(stop, transmit), timeout=2))
    assert transmitted == [encode(1, 7, 2, 1, 0)]
    assert attempts == [{"kind": "ack", "command_id": "x"}] * 2

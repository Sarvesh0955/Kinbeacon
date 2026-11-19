from datetime import datetime, timezone
import pytest
import httpx

from app.models.entities import Anchor
from app.transport.http import HttpAnchorTransport, parse_timestamp
from app.transport.mock import MockAnchorTransport
from app.zoning.models import RawSighting


def test_parse_timestamp():
    dt = parse_timestamp("2026-11-19T00:15:30.123Z")
    assert dt is not None
    assert dt.tzinfo is not None
    assert dt.year == 2026

    # Test epoch float
    dt2 = parse_timestamp(1700000000.0)
    assert dt2 is not None
    assert dt2.year >= 2023

    # Test invalid
    assert parse_timestamp("invalid-date") is None
    assert parse_timestamp(None) is None


@pytest.mark.asyncio
async def test_mock_transport():
    mock = MockAnchorTransport()
    a1 = Anchor(anchor_id="A1", base_url="http://mock1:5000", enabled=True)
    a2 = Anchor(anchor_id="A2", base_url="http://mock2:5000", enabled=True)

    now = datetime.now(timezone.utc)
    mock.set_anchor_sightings("A1", [RawSighting("A1", now, -55)])
    mock.set_anchor_failure("A2", "TIMEOUT")

    results = await mock.search_all("DEV1", [a1, a2])
    assert results["A1"].outcome == "OK"
    assert len(results["A1"].sightings) == 1
    assert results["A2"].outcome == "TIMEOUT"


@pytest.mark.asyncio
async def test_http_transport_mocked_responses():
    now_iso = datetime.now(timezone.utc).isoformat()

    def mock_handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "anchor1" in url_str and request.method == "POST":
            return httpx.Response(
                200,
                json={
                    "anchor_id": "A1",
                    "device_id": "PHONE1",
                    "record_count": 1,
                    "records": [{"rssi": -58, "timestamp": now_iso}],
                },
            )
        elif "anchor2" in url_str and request.method == "POST":
            # 404 defensive empty
            return httpx.Response(404)
        elif "anchor3" in url_str and request.method == "POST":
            # Device mismatch
            return httpx.Response(
                200,
                json={
                    "anchor_id": "A3",
                    "device_id": "DIFFERENT_DEV",
                    "record_count": 1,
                    "records": [{"rssi": -58, "timestamp": now_iso}],
                },
            )
        elif "status" in url_str and request.method == "GET":
            return httpx.Response(
                200,
                json={"anchor_id": "A1", "ble_scanner": "running"},
            )
        return httpx.Response(500)

    client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
    transport = HttpAnchorTransport(client=client)

    a1 = Anchor(anchor_id="A1", base_url="http://anchor1:5000", enabled=True)
    a2 = Anchor(anchor_id="A2", base_url="http://anchor2:5000", enabled=True)
    a3 = Anchor(anchor_id="A3", base_url="http://anchor3:5000", enabled=True)

    results = await transport.search_all("PHONE1", [a1, a2, a3])
    assert results["A1"].outcome == "OK"
    assert len(results["A1"].sightings) == 1
    assert results["A2"].outcome == "EMPTY"
    assert results["A3"].outcome == "ERROR"
    assert "Device ID mismatch" in results["A3"].error

    # Test verify
    v_res = await transport.verify_anchor(a1)
    assert v_res.verified is True
    assert v_res.ble_scanner == "running"

    await transport.close()

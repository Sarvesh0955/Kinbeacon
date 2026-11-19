from datetime import datetime, timezone
import pytest
from httpx import AsyncClient
from app.zoning.models import RawSighting


@pytest.mark.asyncio
async def test_health_endpoints(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

    resp_v1 = await client.get("/api/v1/health")
    assert resp_v1.status_code == 200
    assert resp_v1.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_zone_crud(client: AsyncClient):
    # Create Zone 1
    resp = await client.post(
        "/api/v1/zones",
        json={"id": 1, "name": "Zone 1", "centroid_x": 10.0, "centroid_y": 10.0},
    )
    assert resp.status_code == 201
    assert resp.json()["id"] == 1

    # Create Zone 2 adjacent to Zone 1
    resp2 = await client.post(
        "/api/v1/zones",
        json={"id": 2, "name": "Zone 2", "centroid_x": 30.0, "centroid_y": 10.0, "adjacent_to": [1]},
    )
    assert resp2.status_code == 201
    assert 1 in resp2.json()["adjacent_zone_ids"]

    # List zones
    list_resp = await client.get("/api/v1/zones")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 2


@pytest.mark.asyncio
async def test_device_crud(client: AsyncClient):
    resp = await client.post(
        "/api/v1/devices",
        json={"device_id": "KINBEACON-PHONE1", "display_name": "Test Phone"},
    )
    assert resp.status_code == 201
    assert resp.json()["device_id"] == "KINBEACON-PHONE1"

    get_resp = await client.get("/api/v1/devices/KINBEACON-PHONE1")
    assert get_resp.status_code == 200
    assert get_resp.json()["display_name"] == "Test Phone"

    # Soft delete
    del_resp = await client.delete("/api/v1/devices/KINBEACON-PHONE1")
    assert del_resp.status_code == 204


@pytest.mark.asyncio
async def test_anchor_crud_and_verify(client: AsyncClient, mock_transport):
    # First create a zone
    await client.post("/api/v1/zones", json={"id": 1, "name": "Zone 1"})

    # Create anchor
    resp = await client.post(
        "/api/v1/anchors",
        json={
            "anchor_id": "ANCHOR-LAPTOP-01",
            "base_url": "http://192.168.1.50:5000",
            "zone_id": 1,
            "x": 10.0,
            "y": 10.0,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["anchor_id"] == "ANCHOR-LAPTOP-01"
    assert data["verified"] is True

    # Test verify endpoint
    v_resp = await client.post("/api/v1/anchors/ANCHOR-LAPTOP-01/verify")
    assert v_resp.status_code == 200
    assert v_resp.json()["verified"] is True


@pytest.mark.asyncio
async def test_venue_seed(client: AsyncClient):
    seed_payload = {
        "zones": [
            {
                "id": 10,
                "name": "Zone 10",
                "centroid": {"x": 10.0, "y": 10.0},
                "metadata": {"shape": "square", "side_m": 20},
                "adjacent_to": [],
            }
        ],
        "anchors": [
            {
                "anchor_id": "ANCHOR-SEED-01",
                "base_url": "http://192.168.1.100:5000",
                "zone_id": 10,
                "x": 10.0,
                "y": 10.0,
                "enabled": True,
            }
        ],
        "devices": [{"device_id": "SEED-DEV-1", "display_name": "Seeded Device"}],
    }

    resp = await client.post("/api/v1/admin/seed", json=seed_payload)
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["zones_created"] == 1
    assert res_data["anchors_created"] == 1
    assert res_data["devices_created"] == 1


@pytest.mark.asyncio
async def test_searches_workflow(client: AsyncClient, mock_transport):
    # 1. Unknown device returns 404
    resp_404 = await client.post("/api/v1/searches", json={"device_id": "NON-EXISTENT"})
    assert resp_404.status_code == 404

    # 2. Setup zone, anchor, device
    await client.post("/api/v1/zones", json={"id": 1, "name": "Zone 1"})
    await client.post(
        "/api/v1/anchors",
        json={
            "anchor_id": "ANCHOR-01",
            "base_url": "http://mock-anchor:5000",
            "zone_id": 1,
            "x": 10.0,
            "y": 10.0,
        },
    )
    await client.post(
        "/api/v1/devices",
        json={"device_id": "KINBEACON-PHONE1", "display_name": "Phone 1"},
    )

    # 3. Search when device not detected (EMPTY)
    resp_empty = await client.post(
        "/api/v1/searches", json={"device_id": "KINBEACON-PHONE1"}
    )
    assert resp_empty.status_code == 200
    empty_data = resp_empty.json()
    assert empty_data["zone"] is None
    assert empty_data["confidence"] == 0.0
    assert "NOT_SEEN" in empty_data["flags"]

    # 4. Search with sightings
    now = datetime.now(timezone.utc)
    mock_transport.set_anchor_sightings(
        "ANCHOR-01",
        [
            RawSighting("ANCHOR-01", now, -58),
            RawSighting("ANCHOR-01", now, -56),
        ],
    )

    resp_sighting = await client.post(
        "/api/v1/searches", json={"device_id": "KINBEACON-PHONE1"}
    )
    assert resp_sighting.status_code == 200
    sighting_data = resp_sighting.json()
    assert sighting_data["status"] == "COMPLETED"
    assert sighting_data["zone"]["id"] == 1
    assert sighting_data["confidence"] > 0.0
    assert "SINGLE_ANCHOR" in sighting_data["flags"]
    assert sighting_data["anchors"]["responded"] == 1

    # 5. Fetch search by ID
    search_id = sighting_data["search_id"]
    resp_get = await client.get(f"/api/v1/searches/{search_id}")
    assert resp_get.status_code == 200
    assert resp_get.json()["search_id"] == search_id

    # 6. Fetch search history for device
    resp_history = await client.get("/api/v1/devices/KINBEACON-PHONE1/searches")
    assert resp_history.status_code == 200
    assert len(resp_history.json()) >= 2


@pytest.mark.asyncio
async def test_api_key_auth(client: AsyncClient, monkeypatch):
    from app.core.config import settings

    # When api_key is configured
    monkeypatch.setattr(settings, "api_key", "secret-token")

    # Request without key fails with 401
    resp_unauth = await client.get("/api/v1/zones")
    assert resp_unauth.status_code == 401

    # Request with wrong key fails with 401
    resp_wrong = await client.get("/api/v1/zones", headers={"X-API-Key": "wrong"})
    assert resp_wrong.status_code == 401

    # Request with valid key succeeds
    resp_ok = await client.get("/api/v1/zones", headers={"X-API-Key": "secret-token"})
    assert resp_ok.status_code == 200

    # Public health check remains open without key
    resp_health = await client.get("/api/v1/health")
    assert resp_health.status_code == 200

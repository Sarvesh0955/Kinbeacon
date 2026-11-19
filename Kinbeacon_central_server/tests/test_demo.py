from fastapi.testclient import TestClient

from app.api.v1 import demo
from app.main import create_app

BASE = "/api/v1/demo"


def test_lan_rehearsal_and_reunion():
    client = TestClient(create_app())
    assert client.get(BASE + "/state").json()["incident"] is None
    payload = {"incident_id": 11, "mode": "lan"}
    response = client.post(BASE + "/find", json=payload)
    assert response.status_code == 200
    incident = response.json()
    assert incident["status"] == "located"
    assert incident["result"]["landmark"] == "Blue Pavilion"
    assert incident["result"]["radius_m"] == 10
    assert incident["result"]["source"] == "simulated"
    assert client.post(BASE + "/find", json=payload).json() == incident
    assert client.post(BASE + "/find", json={**payload, "incident_id": 12}).status_code == 409
    assert client.get(BASE + "/anchor/commands").json() == []
    client.post(BASE + "/anchor/events", json={"kind": "sighting", "rssi": -61})
    assert client.get(BASE + "/state").json()["anchor_sighting"]["rssi"] == -61

    for _ in range(2):
        assert client.post(BASE + "/reunite", json=payload).json()["status"] == "reunited"
    assert client.post(BASE + "/find", json={**payload, "incident_id": 12}).json()["status"] == "located"
    assert client.post(BASE + "/find", json=payload).json()["status"] == "reunited"


def test_ble_first_result_commands_timeout_and_fallback(monkeypatch):
    now = 1000
    monkeypatch.setattr(demo, "time", lambda: now)
    client = TestClient(create_app())
    publish = lambda payload: client.post(BASE + "/anchor/events", json=payload)
    request = {"kind": "find_request", "incident_id": 21}
    assert publish(request).status_code == 200
    assert publish(request).status_code == 200
    [target] = client.get(BASE + "/anchor/commands").json()
    assert target["kind"] == "find_target"
    assert target["expires_at"] == 1010
    incident = client.post(BASE + "/find", json={"incident_id": 21, "mode": "ble"}).json()
    assert incident["status"] == "searching"
    publish({"kind": "ack", "command_id": target["command_id"]})
    assert client.get(BASE + "/anchor/commands").json() == []
    uplink = {"kind": "uplink", "incident_id": 21, "lat": 12.00024, "lon": 77.00018}
    assert publish({**uplink, "lat": 100}).status_code == 422
    assert publish(uplink).status_code == 200
    assert publish({**uplink, "lat": 0}).status_code == 200
    [result] = client.get(BASE + "/anchor/commands").json()
    assert (result["kind"], result["lat"], result["landmark_index"]) == ("loc_result", uplink["lat"], 1)
    assert client.get(BASE + "/state").json()["incident"]["result"]["source"] == "ble"
    client.post(BASE + "/reunite", json={"incident_id": 21})
    assert client.get(BASE + "/anchor/commands").json() == []
    publish({**request, "incident_id": 22})
    now += 10
    timed_out = client.get(BASE + "/state").json()["incident"]
    assert timed_out["status"] == "timed_out"
    assert timed_out["result"] is None
    publish({**uplink, "incident_id": 22})
    assert client.get(BASE + "/state").json()["incident"] == timed_out
    fallback = client.post(BASE + "/find", json={"incident_id": 23, "mode": "lan"}).json()
    assert fallback["result"]["source"] == "simulated"
    now += 600
    assert client.get(BASE + "/state").json()["incident"] is None

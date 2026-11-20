from fastapi.testclient import TestClient

from app.api.v1 import live_find
from app.main import create_app


BASE = "/api/v1/live-find"


def auth(key):
    return {"Authorization": f"Bearer {key}"}


def test_fixed_code_pairs_only_to_the_waiting_guardian():
    client = TestClient(create_app())
    first = client.post(BASE + "/sessions").json()
    assert first["invite"] == "123456"
    assert client.post(BASE + "/sessions").status_code == 409

    pair = {"invite": "123456", "publisher_key": "a" * 43}
    assert client.post(BASE + "/pair", json={**pair, "invite": "000000"}).status_code == 404
    assert client.post(BASE + "/pair", json=pair).json() == {"session_id": first["session_id"]}

    second = client.post(BASE + "/sessions").json()
    assert second["invite"] == "123456"
    assert client.post(BASE + "/pair", json=pair).json() == {"session_id": first["session_id"]}
    assert client.post(BASE + "/pair", json={**pair, "publisher_key": "b" * 43}).json() == {
        "session_id": second["session_id"],
    }


def test_paired_live_positions_update_only_for_the_guardian(monkeypatch):
    now = 1000.0
    monkeypatch.setattr(live_find, "monotonic", lambda: now)
    client = TestClient(create_app())
    session = client.post(BASE + "/sessions").json()
    path = BASE + "/sessions/" + session["session_id"]
    guardian = auth(session["guardian_key"])
    wearable_key = "a" * 43
    wearable = auth(wearable_key)

    assert client.get(path).status_code == 404
    assert client.get(path, headers=guardian).json() == {"paired": False, "position": None}
    pair = {"invite": session["invite"], "publisher_key": wearable_key}
    assert client.post(BASE + "/pair", json=pair).json() == {"session_id": session["session_id"]}
    assert client.post(BASE + "/pair", json=pair).status_code == 200
    assert client.post(BASE + "/pair", json={**pair, "publisher_key": "b" * 43}).status_code == 404
    assert client.get(path, headers=wearable).status_code == 404
    assert client.head(path, headers=wearable).status_code == 204

    fix = {"lat": 12.0, "lon": 77.0, "accuracy_m": 3.5, "sample_id": 123, "age_ms": 100}
    assert client.put(path + "/position", headers=guardian, json=fix).status_code == 404
    assert client.put(path + "/position", headers=wearable, json=fix).status_code == 204
    now += 1
    second = {**fix, "lat": 12.0001, "sample_id": 124}
    assert client.put(path + "/position", headers=wearable, json=second).status_code == 204
    now += 6
    assert client.put(path + "/position", headers=wearable, json=fix).status_code == 204
    result = client.get(path, headers=guardian)
    assert result.headers["cache-control"] == "no-store"
    assert result.json() == {"paired": True, "position": {**second, "age_ms": 6100}}

    assert client.delete(path, headers=wearable).status_code == 204
    assert client.get(path, headers=guardian).status_code == 404
    assert client.post(BASE + "/pair", json=pair).status_code == 404


def test_session_expires_when_guardian_leaves(monkeypatch):
    now = 1000.0
    monkeypatch.setattr(live_find, "monotonic", lambda: now)
    client = TestClient(create_app())
    session = client.post(BASE + "/sessions").json()
    path = BASE + "/sessions/" + session["session_id"]
    wearable_key = "a" * 43
    pair = {"invite": session["invite"], "publisher_key": wearable_key}
    assert client.post(BASE + "/pair", json=pair).status_code == 200

    now += live_find.GUARDIAN_IDLE_SECONDS - 1
    assert client.head(path, headers=auth(wearable_key)).status_code == 204
    now += 1
    assert client.head(path, headers=auth(wearable_key)).status_code == 404
    assert client.get(path, headers=auth(session["guardian_key"])).status_code == 404
    assert client.post(BASE + "/pair", json=pair).status_code == 404

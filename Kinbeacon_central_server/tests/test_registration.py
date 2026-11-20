from base64 import b64decode, b64encode
from hashlib import sha256
from time import time_ns

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from app.core.config import settings


def registration_payload(private_key):
    public_der = private_key.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return {
        "client_pub_key": b64encode(public_der).decode("ascii"),
        "cipher_suite": "AES-128-ECB-TRUNC64",
    }


async def test_registration_matches_wearable_broadcast(client):
    phone_key = ec.generate_private_key(ec.SECP256R1())
    started_at = time_ns() // 1_000_000
    response = await client.post("/api/register", json=registration_payload(phone_key))

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    result = response.json()
    assert started_at <= result["server_time_ms"] <= time_ns() // 1_000_000
    assert result["rotation_interval_sec"] == 3

    server_key = serialization.load_der_public_key(b64decode(result["server_pub_key"], validate=True))
    phone_shared_key = sha256(phone_key.exchange(ec.ECDH(), server_key)).digest()[:16]
    cipher = Cipher(algorithms.AES(phone_shared_key), modes.ECB()).encryptor()
    device_id = "kb-" + cipher.update(bytes(16))[:8].hex()
    assert result["device_id"] == device_id

    device = await client.get(f"/api/v1/devices/{device_id}")
    assert device.status_code == 200
    assert device.json()["device_id"] == device_id
    assert device.json()["metadata_json"] == {}


async def test_registration_rejects_bad_keys_and_unsupported_suite(client):
    valid = registration_payload(ec.generate_private_key(ec.SECP256R1()))
    wrong_curve = registration_payload(ec.generate_private_key(ec.SECP384R1()))

    for payload in (wrong_curve, {**valid, "client_pub_key": "%%%"}, {**valid, "cipher_suite": "other"}):
        response = await client.post("/api/register", json=payload)
        assert response.status_code == 422
    assert (await client.get("/api/v1/devices")).json() == []


async def test_registration_respects_configured_api_key(client, monkeypatch):
    monkeypatch.setattr(settings, "api_key", "test-key")
    request = registration_payload(ec.generate_private_key(ec.SECP256R1()))

    assert (await client.post("/api/register", json=request)).status_code == 401
    response = await client.post("/api/register", json=request, headers={"X-API-Key": "test-key"})
    assert response.status_code == 200

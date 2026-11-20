"""ECDH enrollment for the Android Registered Wearable demo."""

from base64 import b64decode, b64encode
from hashlib import sha256
from time import time_ns
from typing import Annotated, Literal

from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, get_transport
from app.core.auth import verify_api_key
from app.schemas.device import DeviceCreate
from app.services.registry_service import RegistryService
from app.transport.base import AnchorTransport

router = APIRouter(tags=["Wearable registration"], dependencies=[Depends(verify_api_key)])


class RegistrationRequest(BaseModel):
    client_pub_key: Annotated[str, Field(min_length=1, max_length=256)]
    cipher_suite: Literal["AES-128-ECB-TRUNC64"]


class RegistrationResponse(BaseModel):
    device_id: str
    server_pub_key: str
    server_time_ms: int
    rotation_interval_sec: int = 3


@router.post("/api/register", response_model=RegistrationResponse)
async def register(
    data: RegistrationRequest,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    transport: Annotated[AnchorTransport, Depends(get_transport)],
) -> RegistrationResponse:
    try:
        client_key = serialization.load_der_public_key(b64decode(data.client_pub_key, validate=True))
    except (ValueError, UnsupportedAlgorithm) as exc:
        raise HTTPException(422, "Expected a Base64 DER-encoded P-256 public key") from exc
    if not isinstance(client_key, ec.EllipticCurvePublicKey) or not isinstance(client_key.curve, ec.SECP256R1):
        raise HTTPException(422, "Expected a Base64 DER-encoded P-256 public key")

    server_key = ec.generate_private_key(ec.SECP256R1())
    public_der = server_key.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    shared_key = sha256(server_key.exchange(ec.ECDH(), client_key)).digest()[:16]
    # Android currently broadcasts the counter-zero token in the default hex framing.
    encryptor = Cipher(algorithms.AES(shared_key), modes.ECB()).encryptor()
    token = (encryptor.update(bytes(16)) + encryptor.finalize())[:8]
    device_id = "kb-" + token.hex()
    await RegistryService(session, transport).create_device(DeviceCreate(device_id=device_id))

    response.headers["Cache-Control"] = "no-store"
    return RegistrationResponse(
        device_id=device_id,
        server_pub_key=b64encode(public_der).decode("ascii"),
        server_time_ms=time_ns() // 1_000_000,
    )

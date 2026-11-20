"""Short-lived, paired location sharing for foreground Live Find sessions."""

from dataclasses import dataclass
from secrets import compare_digest, token_urlsafe
from time import monotonic
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

router = APIRouter(prefix="/live-find", tags=["Live Find"])
bearer = HTTPBearer(auto_error=False)
Credential = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]
PublisherKey = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{43}$")]

INVITE_SECONDS = 5 * 60
SESSION_SECONDS = 30 * 60
GUARDIAN_IDLE_SECONDS = 60
MAX_SESSIONS = 128


class Pair(BaseModel):
    invite: Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{22}$")]
    publisher_key: PublisherKey


class Position(BaseModel):
    lat: Annotated[float, Field(ge=-90, le=90)]
    lon: Annotated[float, Field(ge=-180, le=180)]
    accuracy_m: Annotated[float, Field(gt=0, le=100_000)]
    sample_id: Annotated[int, Field(ge=0, le=2**63 - 1)]
    age_ms: Annotated[int, Field(ge=0, le=10_000)]


@dataclass
class Session:
    id: str
    guardian_key: str
    invite: str
    created_at: float
    guardian_seen_at: float
    publisher_key: str | None = None
    position: Position | None = None
    received_at: float = 0


class LiveFind:
    def __init__(self):
        self.sessions: dict[str, Session] = {}

    def expire(self):
        now = monotonic()
        self.sessions = {
            key: session
            for key, session in self.sessions.items()
            if now - session.created_at < SESSION_SECONDS
            and (
                now - session.created_at < INVITE_SECONDS
                if session.publisher_key is None
                else now - session.guardian_seen_at < GUARDIAN_IDLE_SECONDS
            )
        }

    def authorized(self, session_id: str, auth, role: str | None = None) -> Session:
        self.expire()
        session = self.sessions.get(session_id)
        if session and auth and auth.credentials.isascii():
            keys = []
            if role != "wearable":
                keys.append(session.guardian_key)
            if role != "guardian" and session.publisher_key is not None:
                keys.append(session.publisher_key)
            if any(compare_digest(auth.credentials, key) for key in keys):
                return session
        raise HTTPException(404, "Live Find session unavailable")


@router.post("/sessions", status_code=201)
async def create(request: Request, response: Response):
    live: LiveFind = request.app.state.live_find
    live.expire()
    if len(live.sessions) >= MAX_SESSIONS:
        raise HTTPException(503, "Live Find is busy")
    now = monotonic()
    session = Session(token_urlsafe(16), token_urlsafe(32), token_urlsafe(16), now, now)
    live.sessions[session.id] = session
    response.headers["Cache-Control"] = "no-store"
    return {
        "session_id": session.id,
        "guardian_key": session.guardian_key,
        "invite": session.invite,
    }


@router.post("/pair")
async def pair(data: Pair, request: Request, response: Response):
    live: LiveFind = request.app.state.live_find
    live.expire()
    for session in live.sessions.values():
        if not compare_digest(session.invite, data.invite):
            continue
        if session.publisher_key is None:
            session.publisher_key = data.publisher_key
            session.guardian_seen_at = monotonic()
        if compare_digest(session.publisher_key, data.publisher_key):
            response.headers["Cache-Control"] = "no-store"
            return {"session_id": session.id}
        break
    raise HTTPException(404, "Live Find pairing code unavailable")


@router.put("/sessions/{session_id}/position", status_code=204)
async def publish(session_id: str, data: Position, auth: Credential, request: Request):
    live: LiveFind = request.app.state.live_find
    session = live.authorized(session_id, auth, "wearable")
    if session.position is None or data.sample_id > session.position.sample_id:
        session.position = data
        session.received_at = monotonic()


@router.get("/sessions/{session_id}")
async def read(session_id: str, auth: Credential, request: Request, response: Response):
    live: LiveFind = request.app.state.live_find
    session = live.authorized(session_id, auth, "guardian")
    now = monotonic()
    session.guardian_seen_at = now
    response.headers["Cache-Control"] = "no-store"
    position = session.position
    return {
        "paired": session.publisher_key is not None,
        "position": position.model_dump() | {
            "age_ms": position.age_ms + int((now - session.received_at) * 1000),
        } if position else None,
    }


@router.head("/sessions/{session_id}", status_code=204)
async def check_pairing(session_id: str, auth: Credential, request: Request):
    live: LiveFind = request.app.state.live_find
    live.authorized(session_id, auth, "wearable")


@router.delete("/sessions/{session_id}", status_code=204)
async def stop(session_id: str, auth: Credential, request: Request):
    live: LiveFind = request.app.state.live_find
    session = live.authorized(session_id, auth)
    del live.sessions[session.id]

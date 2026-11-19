from typing import AsyncGenerator
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db_session
from app.transport.base import AnchorTransport
from app.transport.http import HttpAnchorTransport

# Global default transport (singleton)
_global_transport: AnchorTransport = HttpAnchorTransport()


def get_transport() -> AnchorTransport:
    return _global_transport


def set_transport(transport: AnchorTransport) -> None:
    global _global_transport
    _global_transport = transport

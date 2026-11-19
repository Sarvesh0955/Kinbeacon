from typing import Any, Dict, List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db_session, get_transport
from app.schemas.anchor import (
    AnchorCreate,
    AnchorResponse,
    AnchorUpdate,
    AnchorVerificationResult,
)
from app.services.health_service import HealthService
from app.services.registry_service import RegistryService
from app.transport.base import AnchorTransport

router = APIRouter(prefix="/anchors", tags=["Anchors"])


@router.post("", response_model=AnchorResponse, status_code=status.HTTP_201_CREATED)
async def create_anchor(
    data: AnchorCreate,
    verify: bool = Query(True, description="Verify anchor via /api/v1/status on registration"),
    session: AsyncSession = Depends(get_db_session),
    transport: AnchorTransport = Depends(get_transport),
):
    service = RegistryService(session, transport)
    return await service.create_anchor(data, verify=verify)


@router.get("", response_model=List[AnchorResponse])
async def list_anchors(
    session: AsyncSession = Depends(get_db_session),
    transport: AnchorTransport = Depends(get_transport),
):
    service = RegistryService(session, transport)
    return await service.list_anchors()


@router.get("/status", response_model=Dict[str, Any])
async def get_anchors_status(
    session: AsyncSession = Depends(get_db_session),
    transport: AnchorTransport = Depends(get_transport),
):
    service = HealthService(session, transport)
    return await service.check_fleet_health()


@router.get("/{anchor_id}", response_model=AnchorResponse)
async def get_anchor(
    anchor_id: str,
    session: AsyncSession = Depends(get_db_session),
    transport: AnchorTransport = Depends(get_transport),
):
    service = RegistryService(session, transport)
    return await service.get_anchor(anchor_id)


@router.patch("/{anchor_id}", response_model=AnchorResponse)
async def update_anchor(
    anchor_id: str,
    data: AnchorUpdate,
    verify: bool = Query(True, description="Re-verify anchor on update"),
    session: AsyncSession = Depends(get_db_session),
    transport: AnchorTransport = Depends(get_transport),
):
    service = RegistryService(session, transport)
    return await service.update_anchor(anchor_id, data, verify=verify)


@router.post("/{anchor_id}/verify", response_model=AnchorVerificationResult)
async def verify_anchor(
    anchor_id: str,
    session: AsyncSession = Depends(get_db_session),
    transport: AnchorTransport = Depends(get_transport),
):
    service = RegistryService(session, transport)
    return await service.verify_anchor_by_id(anchor_id)


@router.delete("/{anchor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_anchor(
    anchor_id: str,
    session: AsyncSession = Depends(get_db_session),
    transport: AnchorTransport = Depends(get_transport),
):
    service = RegistryService(session, transport)
    await service.delete_anchor(anchor_id)

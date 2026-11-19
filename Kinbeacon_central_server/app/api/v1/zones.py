from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db_session, get_transport
from app.schemas.zone import ZoneCreate, ZoneResponse
from app.services.registry_service import RegistryService
from app.transport.base import AnchorTransport

router = APIRouter(prefix="/zones", tags=["Zones"])


@router.post("", response_model=ZoneResponse, status_code=status.HTTP_201_CREATED)
async def create_zone(
    data: ZoneCreate,
    session: AsyncSession = Depends(get_db_session),
    transport: AnchorTransport = Depends(get_transport),
):
    service = RegistryService(session, transport)
    return await service.create_zone(data)


@router.get("", response_model=List[ZoneResponse])
async def list_zones(
    session: AsyncSession = Depends(get_db_session),
    transport: AnchorTransport = Depends(get_transport),
):
    service = RegistryService(session, transport)
    return await service.list_zones()


@router.get("/{zone_id}", response_model=ZoneResponse)
async def get_zone(
    zone_id: int,
    session: AsyncSession = Depends(get_db_session),
    transport: AnchorTransport = Depends(get_transport),
):
    service = RegistryService(session, transport)
    return await service.get_zone(zone_id)

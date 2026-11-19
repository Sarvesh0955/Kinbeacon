from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db_session, get_transport
from app.schemas.seed import VenueSeedRequest, VenueSeedResponse
from app.services.registry_service import RegistryService
from app.transport.base import AnchorTransport

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.post("/seed", response_model=VenueSeedResponse, status_code=status.HTTP_200_OK)
async def seed_venue(
    data: VenueSeedRequest,
    session: AsyncSession = Depends(get_db_session),
    transport: AnchorTransport = Depends(get_transport),
):
    service = RegistryService(session, transport)
    return await service.seed_venue(data)

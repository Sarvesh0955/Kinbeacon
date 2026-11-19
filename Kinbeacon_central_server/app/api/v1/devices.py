from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db_session, get_transport
from app.schemas.device import DeviceCreate, DeviceResponse, DeviceUpdate
from app.services.registry_service import RegistryService
from app.transport.base import AnchorTransport

router = APIRouter(prefix="/devices", tags=["Devices"])


@router.post("", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
async def create_device(
    data: DeviceCreate,
    session: AsyncSession = Depends(get_db_session),
    transport: AnchorTransport = Depends(get_transport),
):
    service = RegistryService(session, transport)
    return await service.create_device(data)


@router.get("", response_model=List[DeviceResponse])
async def list_devices(
    session: AsyncSession = Depends(get_db_session),
    transport: AnchorTransport = Depends(get_transport),
):
    service = RegistryService(session, transport)
    return await service.list_devices()


@router.get("/{device_id}", response_model=DeviceResponse)
async def get_device(
    device_id: str,
    session: AsyncSession = Depends(get_db_session),
    transport: AnchorTransport = Depends(get_transport),
):
    service = RegistryService(session, transport)
    return await service.get_device(device_id)


@router.patch("/{device_id}", response_model=DeviceResponse)
async def update_device(
    device_id: str,
    data: DeviceUpdate,
    session: AsyncSession = Depends(get_db_session),
    transport: AnchorTransport = Depends(get_transport),
):
    service = RegistryService(session, transport)
    return await service.update_device(device_id, data)


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(
    device_id: str,
    session: AsyncSession = Depends(get_db_session),
    transport: AnchorTransport = Depends(get_transport),
):
    service = RegistryService(session, transport)
    await service.delete_device(device_id)

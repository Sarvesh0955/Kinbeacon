from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.entities import Device
from app.schemas.device import DeviceCreate, DeviceUpdate


class DeviceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: DeviceCreate) -> Device:
        dev = Device(
            device_id=data.device_id,
            display_name=data.display_name,
            guardian_ref=data.guardian_ref,
            status=data.status,
            metadata_json=data.metadata_json,
        )
        self.session.add(dev)
        await self.session.flush()
        return dev

    async def get_by_device_id(self, device_id: str) -> Optional[Device]:
        stmt = select(Device).where(Device.device_id == device_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_all(self) -> List[Device]:
        stmt = select(Device).order_by(Device.id)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def update(self, dev: Device, data: DeviceUpdate) -> Device:
        if data.display_name is not None:
            dev.display_name = data.display_name
        if data.guardian_ref is not None:
            dev.guardian_ref = data.guardian_ref
        if data.status is not None:
            dev.status = data.status
        if data.metadata_json is not None:
            dev.metadata_json = data.metadata_json
        await self.session.flush()
        return dev

    async def soft_delete(self, dev: Device) -> None:
        dev.status = "INACTIVE"
        await self.session.flush()

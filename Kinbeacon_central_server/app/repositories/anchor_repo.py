from datetime import datetime, timedelta, timezone
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.models.entities import Anchor, utcnow
from app.schemas.anchor import AnchorCreate, AnchorUpdate


class AnchorRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: AnchorCreate) -> Anchor:
        anchor = Anchor(
            anchor_id=data.anchor_id,
            base_url=data.base_url.rstrip("/"),
            zone_id=data.zone_id,
            x=data.x,
            y=data.y,
            floor=data.floor,
            enabled=data.enabled,
            metadata_json=data.metadata_json,
        )
        self.session.add(anchor)
        await self.session.flush()
        return anchor

    async def get_by_anchor_id(self, anchor_id: str) -> Optional[Anchor]:
        stmt = select(Anchor).where(Anchor.anchor_id == anchor_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_all(self) -> List[Anchor]:
        stmt = select(Anchor).order_by(Anchor.id)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def get_active(self) -> List[Anchor]:
        now = utcnow()
        stmt = select(Anchor).where(
            Anchor.enabled.is_(True),
            (Anchor.circuit_open_until.is_(None)) | (Anchor.circuit_open_until <= now),
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def update(self, anchor: Anchor, data: AnchorUpdate) -> Anchor:
        if data.base_url is not None:
            anchor.base_url = data.base_url.rstrip("/")
            # IP or URL change resets verified status per section 5.4
            anchor.verified = False
            anchor.verify_note = "URL changed, verification pending"
        if data.zone_id is not None:
            anchor.zone_id = data.zone_id
        if data.x is not None:
            anchor.x = data.x
        if data.y is not None:
            anchor.y = data.y
        if data.floor is not None:
            anchor.floor = data.floor
        if data.enabled is not None:
            anchor.enabled = data.enabled
        if data.metadata_json is not None:
            anchor.metadata_json = data.metadata_json
        await self.session.flush()
        return anchor

    async def record_success(self, anchor: Anchor) -> None:
        anchor.consecutive_failures = 0
        anchor.last_success_at = utcnow()
        anchor.health_state = "UP"
        anchor.circuit_open_until = None
        await self.session.flush()

    async def record_failure(self, anchor: Anchor) -> None:
        anchor.consecutive_failures += 1
        now = utcnow()
        anchor.last_failure_at = now
        if anchor.consecutive_failures >= settings.circuit_breaker_failures:
            anchor.health_state = "DEGRADED"
            anchor.circuit_open_until = now + timedelta(seconds=settings.circuit_breaker_cooldown_s)
        await self.session.flush()

    async def delete(self, anchor: Anchor) -> None:
        await self.session.delete(anchor)

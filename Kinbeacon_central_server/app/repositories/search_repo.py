from datetime import datetime, timedelta, timezone
from typing import List, Optional
import uuid
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.entities import (
    Search,
    SearchAnchorResult,
    SearchZoneHistory,
    Sighting,
    ZoneEstimate,
    utcnow,
)


class SearchRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_search(self, device_id: str, requested_by: Optional[str] = None) -> Search:
        search = Search(
            id=str(uuid.uuid4()),
            device_id=device_id,
            requested_by=requested_by,
            status="RUNNING",
            started_at=utcnow(),
        )
        self.session.add(search)
        await self.session.flush()
        return search

    async def get_by_id(self, search_id: str) -> Optional[Search]:
        stmt = select(Search).where(Search.id == search_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_by_device_id(self, device_id: str, limit: int = 10) -> List[Search]:
        stmt = (
            select(Search)
            .where(Search.device_id == device_id)
            .order_by(Search.started_at.desc())
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def save_anchor_results(self, results: List[SearchAnchorResult]) -> None:
        self.session.add_all(results)
        await self.session.flush()

    async def save_sightings(self, sightings: List[Sighting]) -> None:
        self.session.add_all(sightings)
        await self.session.flush()

    async def save_estimates(self, estimates: List[ZoneEstimate]) -> None:
        self.session.add_all(estimates)
        await self.session.flush()

    async def save_zone_history(self, history: SearchZoneHistory) -> None:
        self.session.add(history)
        await self.session.flush()

    async def purge_older_than(self, ttl_seconds: float) -> int:
        cutoff = utcnow() - timedelta(seconds=ttl_seconds)
        expired_searches = select(Search.id).where(Search.started_at < cutoff)
        await self.session.execute(
            delete(SearchZoneHistory).where(SearchZoneHistory.search_id.in_(expired_searches))
        )
        stmt = delete(Search).where(Search.started_at < cutoff)
        res = await self.session.execute(stmt)
        return res.rowcount

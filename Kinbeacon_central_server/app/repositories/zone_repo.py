from typing import List, Optional, Set
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.entities import Zone, ZoneAdjacency
from app.schemas.zone import ZoneCreate


class ZoneRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: ZoneCreate) -> Zone:
        zone = Zone(
            id=data.id,
            name=data.name,
            centroid_x=data.centroid_x,
            centroid_y=data.centroid_y,
            metadata_json=data.metadata_json,
        )
        self.session.add(zone)
        await self.session.flush()

        for adj_id in data.adjacent_to:
            if adj_id != zone.id:
                await self.add_adjacency(zone.id, adj_id)

        return zone

    async def get_by_id(self, zone_id: int) -> Optional[Zone]:
        stmt = select(Zone).where(Zone.id == zone_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_all(self) -> List[Zone]:
        stmt = select(Zone).order_by(Zone.id)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def add_adjacency(self, zone_a_id: int, zone_b_id: int) -> None:
        a, b = min(zone_a_id, zone_b_id), max(zone_a_id, zone_b_id)
        stmt = select(ZoneAdjacency).where(
            ZoneAdjacency.zone_a_id == a,
            ZoneAdjacency.zone_b_id == b,
        )
        existing = await self.session.execute(stmt)
        if not existing.scalar_one_or_none():
            self.session.add(ZoneAdjacency(zone_a_id=a, zone_b_id=b))

    async def get_adjacent_zone_ids(self, zone_id: int) -> Set[int]:
        stmt = select(ZoneAdjacency).where(
            (ZoneAdjacency.zone_a_id == zone_id) | (ZoneAdjacency.zone_b_id == zone_id)
        )
        res = await self.session.execute(stmt)
        adj_records = res.scalars().all()
        adjacent: Set[int] = set()
        for rec in adj_records:
            if rec.zone_a_id == zone_id:
                adjacent.add(rec.zone_b_id)
            else:
                adjacent.add(rec.zone_a_id)
        return adjacent

    async def delete(self, zone_id: int) -> bool:
        zone = await self.get_by_id(zone_id)
        if not zone:
            return False
        await self.session.delete(zone)
        return True

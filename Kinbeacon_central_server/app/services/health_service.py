from typing import Any, Dict, List
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.entities import Anchor
from app.repositories.anchor_repo import AnchorRepository
from app.transport.base import AnchorTransport


class HealthService:
    def __init__(self, session: AsyncSession, transport: AnchorTransport):
        self.session = session
        self.transport = transport
        self.anchor_repo = AnchorRepository(session)

    async def check_fleet_health(self) -> Dict[str, Any]:
        anchors = await self.anchor_repo.get_all()
        summary = {
            "total_anchors": len(anchors),
            "up": 0,
            "degraded": 0,
            "down": 0,
            "unknown": 0,
            "anchors": [],
        }

        for a in anchors:
            status = a.health_state.lower()
            if status in summary:
                summary[status] += 1
            else:
                summary["unknown"] += 1

            summary["anchors"].append(
                {
                    "anchor_id": a.anchor_id,
                    "zone_id": a.zone_id,
                    "health_state": a.health_state,
                    "is_active": a.is_active,
                    "consecutive_failures": a.consecutive_failures,
                    "verified": a.verified,
                    "last_success_at": a.last_success_at,
                    "last_failure_at": a.last_failure_at,
                }
            )

        return summary

    async def probe_anchor_fleet(self) -> None:
        anchors = await self.anchor_repo.get_all()
        for a in anchors:
            if not a.enabled:
                continue
            health = await self.transport.check_health(a)
            if health == "UP":
                await self.anchor_repo.record_success(a)
            else:
                await self.anchor_repo.record_failure(a)

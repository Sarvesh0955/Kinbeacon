from typing import Dict, List, Optional, Set
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.errors import ConflictError, EntityNotFoundError
from app.core.logging import logger
from app.models.entities import Anchor, Device, Zone, utcnow
from app.repositories.anchor_repo import AnchorRepository
from app.repositories.device_repo import DeviceRepository
from app.repositories.zone_repo import ZoneRepository
from app.schemas.anchor import (
    AnchorCreate,
    AnchorResponse,
    AnchorUpdate,
    AnchorVerificationResult,
)
from app.schemas.device import DeviceCreate, DeviceResponse, DeviceUpdate
from app.schemas.seed import VenueSeedRequest, VenueSeedResponse
from app.schemas.zone import ZoneCreate, ZoneResponse
from app.transport.base import AnchorTransport


class RegistryService:
    def __init__(self, session: AsyncSession, transport: AnchorTransport):
        self.session = session
        self.transport = transport
        self.zone_repo = ZoneRepository(session)
        self.anchor_repo = AnchorRepository(session)
        self.device_repo = DeviceRepository(session)

    # Zone operations
    async def create_zone(self, data: ZoneCreate) -> ZoneResponse:
        existing = await self.zone_repo.get_by_id(data.id) if data.id else None
        if existing:
            raise ConflictError(f"Zone with ID {data.id} already exists")
        zone = await self.zone_repo.create(data)
        adj_ids = await self.zone_repo.get_adjacent_zone_ids(zone.id)
        return ZoneResponse(
            id=zone.id,
            name=zone.name,
            centroid_x=zone.centroid_x,
            centroid_y=zone.centroid_y,
            metadata_json=zone.metadata_json or {},
            created_at=zone.created_at,
            adjacent_zone_ids=list(adj_ids),
        )

    async def get_zone(self, zone_id: int) -> ZoneResponse:
        zone = await self.zone_repo.get_by_id(zone_id)
        if not zone:
            raise EntityNotFoundError("Zone", str(zone_id))
        adj_ids = await self.zone_repo.get_adjacent_zone_ids(zone.id)
        return ZoneResponse(
            id=zone.id,
            name=zone.name,
            centroid_x=zone.centroid_x,
            centroid_y=zone.centroid_y,
            metadata_json=zone.metadata_json or {},
            created_at=zone.created_at,
            adjacent_zone_ids=list(adj_ids),
        )

    async def list_zones(self) -> List[ZoneResponse]:
        zones = await self.zone_repo.get_all()
        result: List[ZoneResponse] = []
        for z in zones:
            adj = await self.zone_repo.get_adjacent_zone_ids(z.id)
            result.append(
                ZoneResponse(
                    id=z.id,
                    name=z.name,
                    centroid_x=z.centroid_x,
                    centroid_y=z.centroid_y,
                    metadata_json=z.metadata_json or {},
                    created_at=z.created_at,
                    adjacent_zone_ids=list(adj),
                )
            )
        return result

    # Anchor operations
    async def create_anchor(self, data: AnchorCreate, verify: bool = True) -> AnchorResponse:
        existing = await self.anchor_repo.get_by_anchor_id(data.anchor_id)
        if existing:
            raise ConflictError(f"Anchor '{data.anchor_id}' already exists")
        if data.zone_id:
            zone = await self.zone_repo.get_by_id(data.zone_id)
            if not zone:
                raise EntityNotFoundError("Zone", str(data.zone_id))

        anchor = await self.anchor_repo.create(data)

        if verify:
            v_res = await self.transport.verify_anchor(anchor)
            anchor.verified = v_res.verified
            anchor.verified_at = utcnow()
            anchor.verify_note = v_res.message
            if v_res.verified:
                anchor.health_state = "UP" if v_res.ble_scanner == "running" else "DEGRADED"
            else:
                anchor.health_state = "DOWN"
            await self.session.flush()

        return self._to_anchor_response(anchor)

    async def get_anchor(self, anchor_id: str) -> AnchorResponse:
        anchor = await self.anchor_repo.get_by_anchor_id(anchor_id)
        if not anchor:
            raise EntityNotFoundError("Anchor", anchor_id)
        return self._to_anchor_response(anchor)

    async def list_anchors(self) -> List[AnchorResponse]:
        anchors = await self.anchor_repo.get_all()
        return [self._to_anchor_response(a) for a in anchors]

    async def update_anchor(self, anchor_id: str, data: AnchorUpdate, verify: bool = True) -> AnchorResponse:
        anchor = await self.anchor_repo.get_by_anchor_id(anchor_id)
        if not anchor:
            raise EntityNotFoundError("Anchor", anchor_id)

        if data.zone_id:
            zone = await self.zone_repo.get_by_id(data.zone_id)
            if not zone:
                raise EntityNotFoundError("Zone", str(data.zone_id))

        updated = await self.anchor_repo.update(anchor, data)

        if verify:
            v_res = await self.transport.verify_anchor(updated)
            updated.verified = v_res.verified
            updated.verified_at = utcnow()
            updated.verify_note = v_res.message
            if v_res.verified:
                updated.health_state = "UP" if v_res.ble_scanner == "running" else "DEGRADED"
            await self.session.flush()

        return self._to_anchor_response(updated)

    async def verify_anchor_by_id(self, anchor_id: str) -> AnchorVerificationResult:
        anchor = await self.anchor_repo.get_by_anchor_id(anchor_id)
        if not anchor:
            raise EntityNotFoundError("Anchor", anchor_id)
        v_res = await self.transport.verify_anchor(anchor)
        anchor.verified = v_res.verified
        anchor.verified_at = utcnow()
        anchor.verify_note = v_res.message
        if v_res.verified:
            anchor.health_state = "UP" if v_res.ble_scanner == "running" else "DEGRADED"
        await self.session.flush()
        return v_res

    async def delete_anchor(self, anchor_id: str) -> None:
        anchor = await self.anchor_repo.get_by_anchor_id(anchor_id)
        if not anchor:
            raise EntityNotFoundError("Anchor", anchor_id)
        await self.anchor_repo.delete(anchor)

    # Device operations
    async def create_device(self, data: DeviceCreate) -> DeviceResponse:
        existing = await self.device_repo.get_by_device_id(data.device_id)
        if existing:
            raise ConflictError(f"Device '{data.device_id}' already exists")
        dev = await self.device_repo.create(data)
        return DeviceResponse.model_validate(dev)

    async def get_device(self, device_id: str) -> DeviceResponse:
        dev = await self.device_repo.get_by_device_id(device_id)
        if not dev:
            raise EntityNotFoundError("Device", device_id)
        return DeviceResponse.model_validate(dev)

    async def list_devices(self) -> List[DeviceResponse]:
        devices = await self.device_repo.get_all()
        return [DeviceResponse.model_validate(d) for d in devices]

    async def update_device(self, device_id: str, data: DeviceUpdate) -> DeviceResponse:
        dev = await self.device_repo.get_by_device_id(device_id)
        if not dev:
            raise EntityNotFoundError("Device", device_id)
        updated = await self.device_repo.update(dev, data)
        return DeviceResponse.model_validate(updated)

    async def delete_device(self, device_id: str) -> None:
        dev = await self.device_repo.get_by_device_id(device_id)
        if not dev:
            raise EntityNotFoundError("Device", device_id)
        await self.device_repo.soft_delete(dev)

    # Seed venue
    async def seed_venue(self, data: VenueSeedRequest) -> VenueSeedResponse:
        zones_count = 0
        adj_count = 0
        for z in data.zones:
            existing = await self.zone_repo.get_by_id(z.id) if z.id else None
            cx = z.centroid.get("x", 0.0) if z.centroid else (z.centroid_x or 0.0)
            cy = z.centroid.get("y", 0.0) if z.centroid else (z.centroid_y or 0.0)
            if not existing:
                await self.zone_repo.create(
                    ZoneCreate(
                        id=z.id,
                        name=z.name,
                        centroid_x=cx,
                        centroid_y=cy,
                        metadata_json=z.metadata,
                        adjacent_to=z.adjacent_to,
                    )
                )
                zones_count += 1
                adj_count += len(z.adjacent_to)

        anchors_count = 0
        verified_count = 0
        for a in data.anchors:
            existing_a = await self.anchor_repo.get_by_anchor_id(a.anchor_id)
            if not existing_a:
                created = await self.create_anchor(
                    AnchorCreate(
                        anchor_id=a.anchor_id,
                        base_url=a.base_url,
                        zone_id=a.zone_id,
                        x=a.x,
                        y=a.y,
                        floor=a.floor,
                        enabled=a.enabled,
                        metadata_json=a.metadata,
                    ),
                    verify=True,
                )
                anchors_count += 1
                if created.verified:
                    verified_count += 1

        devs_count = 0
        for d in data.devices:
            existing_d = await self.device_repo.get_by_device_id(d.device_id)
            if not existing_d:
                await self.device_repo.create(
                    DeviceCreate(
                        device_id=d.device_id,
                        display_name=d.display_name,
                        guardian_ref=d.guardian_ref,
                        status=d.status,
                        metadata_json=d.metadata,
                    )
                )
                devs_count += 1

        return VenueSeedResponse(
            zones_created=zones_count,
            anchors_created=anchors_count,
            devices_created=devs_count,
            adjacencies_created=adj_count,
            verified_anchors=verified_count,
        )

    def _to_anchor_response(self, anchor: Anchor) -> AnchorResponse:
        return AnchorResponse(
            id=anchor.id,
            anchor_id=anchor.anchor_id,
            base_url=anchor.base_url,
            zone_id=anchor.zone_id,
            x=anchor.x,
            y=anchor.y,
            floor=anchor.floor,
            enabled=anchor.enabled,
            verified=anchor.verified,
            verified_at=anchor.verified_at,
            verify_note=anchor.verify_note,
            health_state=anchor.health_state,
            is_active=anchor.is_active,
            consecutive_failures=anchor.consecutive_failures,
            clock_offset_ms=anchor.clock_offset_ms,
            metadata_json=anchor.metadata_json or {},
        )

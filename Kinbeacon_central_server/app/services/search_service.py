from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import ZONE_HISTORY_MINUTES, Settings, settings as global_settings
from app.core.errors import EntityNotFoundError, NoActiveAnchorsError
from app.models.entities import (
    Anchor,
    SearchAnchorResult,
    SearchZoneHistory,
    Sighting,
    ZoneEstimate,
    to_utc,
    utcnow,
)
from app.repositories.anchor_repo import AnchorRepository
from app.repositories.device_repo import DeviceRepository
from app.repositories.search_repo import SearchRepository
from app.repositories.zone_repo import ZoneRepository
from app.schemas.search import (
    AnchorEvidence,
    AnchorsSummary,
    EstimatedPosition,
    SearchRequest,
    SearchResponse,
    ZoneCandidate,
    ZoneHistoryEntry,
    ZoneRef,
)
from app.transport.base import AnchorTransport
from app.transport.models import AnchorSearchResult
from app.zoning.engine import ZoneEngine
from app.zoning.models import AnchorMetadata, RawSighting, ZoneMetadata


class SearchService:
    def __init__(
        self,
        session: AsyncSession,
        transport: AnchorTransport,
        config: Optional[Settings] = None,
    ):
        self.session = session
        self.transport = transport
        self.cfg = config or global_settings
        self.device_repo = DeviceRepository(session)
        self.anchor_repo = AnchorRepository(session)
        self.zone_repo = ZoneRepository(session)
        self.search_repo = SearchRepository(session)
        self.zone_engine = ZoneEngine(self.cfg)

    async def execute_search(self, request: SearchRequest) -> SearchResponse:
        # 1. Validate device exists
        dev = await self.device_repo.get_by_device_id(request.device_id)
        if not dev:
            raise EntityNotFoundError("Device", request.device_id)

        # 2. Select active anchors
        all_anchors = await self.anchor_repo.get_all()
        active_anchors = [a for a in all_anchors if a.is_active]
        if not active_anchors:
            raise NoActiveAnchorsError("No active anchors available for search")

        # 3. Create Search record
        search = await self.search_repo.create_search(
            device_id=request.device_id,
            requested_by=request.requested_by,
        )

        # 4. Fan-out query via transport
        transport_results: Dict[str, AnchorSearchResult] = await self.transport.search_all(
            device_id=request.device_id,
            anchors=active_anchors,
            search_id=search.id,
            deadline_s=self.cfg.global_search_deadline_s,
        )

        # 5. Process anchor outcomes & circuit breaker
        anchor_map: Dict[str, Anchor] = {a.anchor_id: a for a in active_anchors}
        search_anchor_rows: List[SearchAnchorResult] = []
        all_sightings: List[RawSighting] = []

        responded_count = 0
        timed_out_count = 0
        failed_count = 0
        unreachable_anchors: List[str] = [
            a.anchor_id for a in all_anchors if not a.is_active
        ]

        for aid, res in transport_results.items():
            anchor = anchor_map.get(aid)
            if res.outcome in ("OK", "EMPTY"):
                responded_count += 1
                if anchor:
                    await self.anchor_repo.record_success(anchor)
            else:
                if res.outcome == "TIMEOUT":
                    timed_out_count += 1
                else:
                    failed_count += 1
                if anchor:
                    await self.anchor_repo.record_failure(anchor)
                unreachable_anchors.append(aid)

            search_anchor_rows.append(
                SearchAnchorResult(
                    search_id=search.id,
                    anchor_id=aid,
                    outcome=res.outcome,
                    http_status=res.http_status,
                    latency_ms=res.latency_ms,
                    sightings_count=len(res.sightings),
                    dropped_count=res.dropped_count,
                    error=res.error,
                )
            )

            all_sightings.extend(res.sightings)

        await self.search_repo.save_anchor_results(search_anchor_rows)

        # 6. Dedupe & sort sightings
        deduped_map: Dict[tuple, RawSighting] = {}
        for s in all_sightings:
            key = (s.anchor_id, s.observed_at)
            deduped_map[key] = s
        chronological_sightings = sorted(deduped_map.values(), key=lambda s: s.observed_at)

        # 7. Prepare metadata for pure zone engine
        zones = await self.zone_repo.get_all()
        zone_meta_map: Dict[int, ZoneMetadata] = {}
        for z in zones:
            adj = await self.zone_repo.get_adjacent_zone_ids(z.id)
            zone_meta_map[z.id] = ZoneMetadata(
                zone_id=z.id,
                name=z.name,
                centroid_x=z.centroid_x,
                centroid_y=z.centroid_y,
                adjacent_zone_ids=adj,
            )

        anchor_meta_map: Dict[str, AnchorMetadata] = {}
        for a in all_anchors:
            is_reachable = a.anchor_id not in unreachable_anchors
            anchor_meta_map[a.anchor_id] = AnchorMetadata(
                anchor_id=a.anchor_id,
                zone_id=a.zone_id,
                x=a.x,
                y=a.y,
                floor=a.floor,
                is_reachable=is_reachable,
            )

        # 8. Run pure ZoneEngine
        now = utcnow()
        estimate_res = self.zone_engine.estimate(
            sightings=chronological_sightings,
            anchors=anchor_meta_map,
            zones=zone_meta_map,
            now=now,
        )
        zone_history = self._estimate_zone_history(
            chronological_sightings, anchor_meta_map, zone_meta_map, now
        )
        if zone_history:
            await self.search_repo.save_zone_history(
                SearchZoneHistory(
                    search_id=search.id,
                    entries=[entry.model_dump(mode="json") for entry in zone_history],
                )
            )

        # 9. Persist sightings (cap raw sightings per anchor)
        sighting_db_rows: List[Sighting] = []
        by_anchor_counts: Dict[str, int] = {}
        current_cutoff = now - timedelta(seconds=self.cfg.stale_max_s)
        # Reverse to get newest sightings first for persistence cap
        for s in reversed(chronological_sightings):
            if to_utc(s.observed_at) < current_cutoff:
                break
            c = by_anchor_counts.get(s.anchor_id, 0)
            if c < self.cfg.max_raw_sightings_persisted_per_anchor:
                sighting_db_rows.append(
                    Sighting(
                        search_id=search.id,
                        anchor_id=s.anchor_id,
                        device_id=request.device_id,
                        observed_at=s.observed_at,
                        rssi=s.rssi,
                    )
                )
                by_anchor_counts[s.anchor_id] = c + 1

        await self.search_repo.save_sightings(sighting_db_rows)

        # 10. Persist estimates
        estimate_rows: List[ZoneEstimate] = []
        for rank, cand in enumerate(estimate_res.candidates, start=1):
            estimate_rows.append(
                ZoneEstimate(
                    search_id=search.id,
                    zone_id=cand.zone_id,
                    rank=rank,
                    score=round(cand.score, 4),
                    probability=round(cand.probability, 4),
                    confidence=estimate_res.confidence,
                    flags=estimate_res.flags,
                    evidence={a.anchor_id: a.anchor_score for a in estimate_res.anchor_evidence},
                )
            )
        await self.search_repo.save_estimates(estimate_rows)

        # 11. Finalize search status
        targeted_count = len(active_anchors)
        if responded_count == targeted_count:
            search.status = "COMPLETED"
        elif responded_count > 0:
            search.status = "PARTIAL"
        else:
            search.status = "FAILED"

        search.anchors_targeted = targeted_count
        search.anchors_responded = responded_count
        search.completed_at = utcnow()
        await self.session.flush()

        # Build response
        zone_ref = (
            ZoneRef(id=estimate_res.winning_zone.zone_id, name=estimate_res.winning_zone.name)
            if estimate_res.winning_zone
            else None
        )
        pos = (
            EstimatedPosition(
                x=estimate_res.estimated_position["x"],
                y=estimate_res.estimated_position["y"],
                floor=int(estimate_res.estimated_position.get("floor", 0)),
            )
            if estimate_res.estimated_position
            else None
        )

        candidates = [
            ZoneCandidate(
                zone_id=c.zone_id,
                zone_name=c.zone_name,
                score=round(c.score, 4),
                probability=round(c.probability, 4),
            )
            for c in estimate_res.candidates
        ]

        evidence = [
            AnchorEvidence(
                anchor_id=a.anchor_id,
                zone_id=a.zone_id,
                samples_count=a.count,
                smoothed_rssi=round(a.smoothed_rssi, 1),
                latest_timestamp=a.latest_timestamp,
                age_s=round(a.age_s, 1),
                anchor_score=round(a.anchor_score, 4),
            )
            for a in estimate_res.anchor_evidence
        ]

        anchors_summary = AnchorsSummary(
            targeted=targeted_count,
            responded=responded_count,
            timed_out=timed_out_count,
            failed=failed_count,
            unreachable=sorted(list(set(unreachable_anchors))),
        )

        return SearchResponse(
            search_id=search.id,
            device_id=request.device_id,
            status=search.status,
            zone=zone_ref,
            zone_history=zone_history,
            estimated_position=pos,
            confidence=estimate_res.confidence,
            confidence_label=estimate_res.confidence_label,
            last_seen_at=estimate_res.last_seen_at,
            age_s=estimate_res.age_s,
            candidates=candidates,
            evidence=evidence,
            flags=estimate_res.flags,
            anchors=anchors_summary,
            started_at=search.started_at,
            completed_at=search.completed_at,
        )

    def _estimate_zone_history(
        self,
        sightings: List[RawSighting],
        anchors: Dict[str, AnchorMetadata],
        zones: Dict[int, ZoneMetadata],
        now: datetime,
    ) -> List[ZoneHistoryEntry]:
        minute = timedelta(minutes=1)
        window_start = now - ZONE_HISTORY_MINUTES * minute
        buckets: Dict[int, List[RawSighting]] = {}
        for sighting in sightings:
            observed_at = to_utc(sighting.observed_at)
            if window_start <= observed_at <= now:
                index = min((observed_at - window_start) // minute, ZONE_HISTORY_MINUTES - 1)
                buckets.setdefault(index, []).append(sighting)

        history: List[ZoneHistoryEntry] = []
        for index, bucket in sorted(buckets.items()):
            minute_start = window_start + index * minute
            estimate = self.zone_engine.estimate(bucket, anchors, zones, now=minute_start + minute)
            zone = estimate.winning_zone
            if zone and (not history or history[-1].id != zone.zone_id):
                history.append(ZoneHistoryEntry(id=zone.zone_id, name=zone.name, minute_start=minute_start))
        return history

    async def get_search(self, search_id: str) -> SearchResponse:
        search = await self.search_repo.get_by_id(search_id)
        if not search:
            raise EntityNotFoundError("Search", search_id)

        # Reconstruct response from stored search, results, estimates, sightings
        zone_ref = None
        candidates = []
        confidence = 0.0
        confidence_label = "LOW"
        flags = []
        if search.estimates:
            top_est = search.estimates[0]
            if top_est.zone_id:
                z = await self.zone_repo.get_by_id(top_est.zone_id)
                if z:
                    zone_ref = ZoneRef(id=z.id, name=z.name)
            confidence = top_est.confidence
            flags = top_est.flags or []
            if confidence >= 0.7:
                confidence_label = "HIGH"
            elif confidence >= 0.4:
                confidence_label = "MEDIUM"

            for e in search.estimates:
                z_name = None
                if e.zone_id:
                    z_obj = await self.zone_repo.get_by_id(e.zone_id)
                    z_name = z_obj.name if z_obj else None
                candidates.append(
                    ZoneCandidate(
                        zone_id=e.zone_id,
                        zone_name=z_name,
                        score=e.score,
                        probability=e.probability,
                    )
                )

        timed_out = sum(1 for r in search.results if r.outcome == "TIMEOUT")
        failed = sum(1 for r in search.results if r.outcome == "ERROR")

        anchors_summary = AnchorsSummary(
            targeted=search.anchors_targeted,
            responded=search.anchors_responded,
            timed_out=timed_out,
            failed=failed,
            unreachable=[],
        )

        last_seen = None
        age_s = None
        if search.sightings:
            last_seen = max(to_utc(s.observed_at) for s in search.sightings)
            now = utcnow()
            age_s = max(0.0, (now - last_seen).total_seconds())

        return SearchResponse(
            search_id=search.id,
            device_id=search.device_id,
            status=search.status,
            zone=zone_ref,
            zone_history=search.zone_history.entries if search.zone_history else [],
            confidence=confidence,
            confidence_label=confidence_label,
            last_seen_at=last_seen,
            age_s=round(age_s, 1) if age_s is not None else None,
            candidates=candidates,
            evidence=[],
            flags=flags,
            anchors=anchors_summary,
            started_at=to_utc(search.started_at),
            completed_at=to_utc(search.completed_at),
        )

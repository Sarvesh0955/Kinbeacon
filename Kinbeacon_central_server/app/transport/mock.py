from datetime import datetime, timezone
from typing import Dict, List, Optional
from app.models.entities import Anchor
from app.schemas.anchor import AnchorVerificationResult
from app.transport.base import AnchorTransport
from app.transport.models import AnchorSearchResult
from app.zoning.models import RawSighting


class MockAnchorTransport(AnchorTransport):
    """In-memory anchor transport for testing and offline simulation."""

    def __init__(self):
        self.mock_sightings: Dict[str, List[RawSighting]] = {}
        self.mock_failures: Dict[str, str] = {}  # anchor_id -> outcome (TIMEOUT, ERROR, etc.)
        self.mock_health: Dict[str, str] = {}  # anchor_id -> UP, DEGRADED, DOWN

    def set_anchor_sightings(self, anchor_id: str, sightings: List[RawSighting]) -> None:
        self.mock_sightings[anchor_id] = sightings

    def set_anchor_failure(self, anchor_id: str, outcome: str) -> None:
        self.mock_failures[anchor_id] = outcome

    def set_anchor_health(self, anchor_id: str, health: str) -> None:
        self.mock_health[anchor_id] = health

    async def search_all(
        self,
        device_id: str,
        anchors: List[Anchor],
        search_id: Optional[str] = None,
        deadline_s: Optional[float] = None,
    ) -> Dict[str, AnchorSearchResult]:
        results: Dict[str, AnchorSearchResult] = {}
        for anchor in anchors:
            aid = anchor.anchor_id
            if aid in self.mock_failures:
                fail_type = self.mock_failures[aid]
                results[aid] = AnchorSearchResult(
                    anchor_id=aid,
                    outcome=fail_type,
                    error=f"Simulated {fail_type}",
                )
            elif aid in self.mock_sightings and self.mock_sightings[aid]:
                sightings = self.mock_sightings[aid]
                results[aid] = AnchorSearchResult(
                    anchor_id=aid,
                    outcome="OK",
                    http_status=200,
                    latency_ms=10.0,
                    sightings=sightings,
                )
            else:
                results[aid] = AnchorSearchResult(
                    anchor_id=aid,
                    outcome="EMPTY",
                    http_status=200,
                    latency_ms=10.0,
                    sightings=[],
                )
        return results

    async def verify_anchor(self, anchor: Anchor) -> AnchorVerificationResult:
        if anchor.anchor_id in self.mock_failures:
            return AnchorVerificationResult(
                anchor_id=anchor.anchor_id,
                verified=False,
                message=f"Mock failure: {self.mock_failures[anchor.anchor_id]}",
            )
        return AnchorVerificationResult(
            anchor_id=anchor.anchor_id,
            verified=True,
            status_code=200,
            reported_anchor_id=anchor.anchor_id,
            ble_scanner="running",
            message="Mock verified successfully",
        )

    async def check_health(self, anchor: Anchor) -> str:
        return self.mock_health.get(anchor.anchor_id, "UP")

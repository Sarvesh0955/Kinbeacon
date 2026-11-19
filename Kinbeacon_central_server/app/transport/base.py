from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from app.models.entities import Anchor
from app.schemas.anchor import AnchorVerificationResult
from app.transport.models import AnchorSearchResult


class AnchorTransport(ABC):
    """Abstract interface for communicating with anchor fleet."""

    @abstractmethod
    async def search_all(
        self,
        device_id: str,
        anchors: List[Anchor],
        search_id: Optional[str] = None,
        deadline_s: Optional[float] = None,
    ) -> Dict[str, AnchorSearchResult]:
        """Queries all active anchors for device sightings within a deadline."""
        pass

    @abstractmethod
    async def verify_anchor(self, anchor: Anchor) -> AnchorVerificationResult:
        """Verifies anchor connectivity and identity via its status endpoint."""
        pass

    @abstractmethod
    async def check_health(self, anchor: Anchor) -> str:
        """Checks anchor health state (UP, DEGRADED, DOWN)."""
        pass

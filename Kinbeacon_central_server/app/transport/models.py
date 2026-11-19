from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
from app.zoning.models import RawSighting


@dataclass
class AnchorSearchResult:
    anchor_id: str
    outcome: str  # OK, EMPTY, TIMEOUT, ERROR, SKIPPED
    http_status: Optional[int] = None
    latency_ms: Optional[float] = None
    sightings: List[RawSighting] = field(default_factory=list)
    dropped_count: int = 0
    error: Optional[str] = None

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    device_id: str = Field(..., min_length=1, max_length=64)
    max_age_s: Optional[float] = None
    requested_by: Optional[str] = None


class ZoneCandidate(BaseModel):
    zone_id: Optional[int] = None
    zone_name: Optional[str] = None
    score: float
    probability: float


class AnchorEvidence(BaseModel):
    anchor_id: str
    zone_id: Optional[int] = None
    samples_count: int
    smoothed_rssi: float
    latest_timestamp: datetime
    age_s: float
    anchor_score: float


class AnchorsSummary(BaseModel):
    targeted: int = 0
    responded: int = 0
    timed_out: int = 0
    failed: int = 0
    unreachable: List[str] = Field(default_factory=list)


class EstimatedPosition(BaseModel):
    x: float
    y: float
    floor: int = 0


class ZoneRef(BaseModel):
    id: int
    name: str


class SearchResponse(BaseModel):
    search_id: str
    device_id: str
    status: str  # COMPLETED, PARTIAL, FAILED
    zone: Optional[ZoneRef] = None
    estimated_position: Optional[EstimatedPosition] = None
    confidence: float
    confidence_label: str  # HIGH, MEDIUM, LOW
    last_seen_at: Optional[datetime] = None
    age_s: Optional[float] = None
    candidates: List[ZoneCandidate] = Field(default_factory=list)
    evidence: List[AnchorEvidence] = Field(default_factory=list)
    flags: List[str] = Field(default_factory=list)
    anchors: AnchorsSummary
    started_at: datetime
    completed_at: Optional[datetime] = None

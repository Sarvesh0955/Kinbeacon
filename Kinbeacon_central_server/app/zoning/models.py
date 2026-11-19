from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set


@dataclass
class RawSighting:
    anchor_id: str
    observed_at: datetime
    rssi: int


@dataclass
class AnchorMetadata:
    anchor_id: str
    zone_id: Optional[int]
    x: float = 0.0
    y: float = 0.0
    floor: int = 0
    is_reachable: bool = True


@dataclass
class ZoneMetadata:
    zone_id: int
    name: str
    centroid_x: float = 0.0
    centroid_y: float = 0.0
    adjacent_zone_ids: Set[int] = field(default_factory=set)


@dataclass
class AnchorSummary:
    anchor_id: str
    zone_id: Optional[int]
    count: int
    latest_timestamp: datetime
    age_s: float
    smoothed_rssi: float
    normalized_rssi: float
    anchor_score: float
    x: float = 0.0
    y: float = 0.0
    floor: int = 0


@dataclass
class ZoneScore:
    zone_id: int
    zone_name: str
    score: float
    probability: float
    anchors_count: int


@dataclass
class ZoneEstimateResult:
    winning_zone: Optional[ZoneMetadata]
    confidence: float
    confidence_label: str  # HIGH, MEDIUM, LOW
    estimated_position: Optional[Dict[str, float]]
    last_seen_at: Optional[datetime]
    age_s: Optional[float]
    candidates: List[ZoneScore]
    anchor_evidence: List[AnchorSummary]
    flags: List[str]
    expanding_search_zone_ids: List[int]

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ZoneSeedItem(BaseModel):
    id: Optional[int] = None
    name: str
    centroid: Optional[Dict[str, float]] = None
    centroid_x: Optional[float] = 0.0
    centroid_y: Optional[float] = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)
    adjacent_to: List[int] = Field(default_factory=list)


class AnchorSeedItem(BaseModel):
    anchor_id: str
    base_url: str
    zone_id: Optional[int] = None
    x: float = 0.0
    y: float = 0.0
    floor: int = 0
    enabled: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DeviceSeedItem(BaseModel):
    device_id: str
    display_name: Optional[str] = None
    guardian_ref: Optional[str] = None
    status: str = "ACTIVE"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class VenueSeedRequest(BaseModel):
    zones: List[ZoneSeedItem] = Field(default_factory=list)
    anchors: List[AnchorSeedItem] = Field(default_factory=list)
    devices: List[DeviceSeedItem] = Field(default_factory=list)


class VenueSeedResponse(BaseModel):
    zones_created: int
    anchors_created: int
    devices_created: int
    adjacencies_created: int
    verified_anchors: int

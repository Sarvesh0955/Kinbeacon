from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ZoneBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    centroid_x: float = 0.0
    centroid_y: float = 0.0
    metadata_json: Dict[str, Any] = Field(default_factory=dict)


class ZoneCreate(ZoneBase):
    id: Optional[int] = None
    adjacent_to: List[int] = Field(default_factory=list)


class ZoneResponse(ZoneBase):
    id: int
    created_at: datetime
    adjacent_zone_ids: List[int] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ZoneAdjacencyCreate(BaseModel):
    zone_a_id: int
    zone_b_id: int

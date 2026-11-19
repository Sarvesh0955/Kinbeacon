from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class AnchorBase(BaseModel):
    anchor_id: str = Field(..., min_length=1, max_length=64)
    base_url: str = Field(..., min_length=1, max_length=255)
    zone_id: Optional[int] = None
    x: float = 0.0
    y: float = 0.0
    floor: int = 0
    enabled: bool = True
    metadata_json: Dict[str, Any] = Field(default_factory=dict)


class AnchorCreate(AnchorBase):
    pass


class AnchorUpdate(BaseModel):
    base_url: Optional[str] = None
    zone_id: Optional[int] = None
    x: Optional[float] = None
    y: Optional[float] = None
    floor: Optional[int] = None
    enabled: Optional[bool] = None
    metadata_json: Optional[Dict[str, Any]] = None


class AnchorResponse(AnchorBase):
    id: int
    verified: bool
    verified_at: Optional[datetime] = None
    verify_note: Optional[str] = None
    health_state: str
    is_active: bool
    consecutive_failures: int
    clock_offset_ms: float

    model_config = ConfigDict(from_attributes=True)


class AnchorVerificationResult(BaseModel):
    anchor_id: str
    verified: bool
    status_code: Optional[int] = None
    reported_anchor_id: Optional[str] = None
    ble_scanner: Optional[str] = None
    message: str


# Anchor HTTP Client Contract Schemas
class AnchorRecord(BaseModel):
    rssi: int
    timestamp: str


class AnchorSearchResponse(BaseModel):
    anchor_id: str
    device_id: str
    record_count: int
    records: List[AnchorRecord] = Field(default_factory=list)


class AnchorStatusResponse(BaseModel):
    anchor_id: str
    ble_scanner: Optional[str] = None
    timestamp: Optional[str] = None
    total_records: Optional[int] = None
    retention_minutes: Optional[int] = None

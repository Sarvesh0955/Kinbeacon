from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field


class DeviceBase(BaseModel):
    device_id: str = Field(..., min_length=1, max_length=64)
    display_name: Optional[str] = None
    guardian_ref: Optional[str] = None
    status: str = "ACTIVE"
    metadata_json: Dict[str, Any] = Field(default_factory=dict)


class DeviceCreate(DeviceBase):
    pass


class DeviceUpdate(BaseModel):
    display_name: Optional[str] = None
    guardian_ref: Optional[str] = None
    status: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None


class DeviceResponse(DeviceBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

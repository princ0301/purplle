from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal
from datetime import datetime
import uuid


EventType = Literal[
    "ENTRY", "EXIT", "ZONE_ENTER", "ZONE_EXIT",
    "ZONE_DWELL", "BILLING_QUEUE_JOIN", "BILLING_QUEUE_ABANDON", "REENTRY"
]


class EventMetadata(BaseModel):
    queue_depth: Optional[int] = None
    sku_zone: Optional[str] = None
    session_seq: Optional[int] = None


class Event(BaseModel):
    event_id: uuid.UUID
    store_id: str
    camera_id: str
    visitor_id: str
    event_type: EventType
    timestamp: datetime
    zone_id: Optional[str] = None
    dwell_ms: int = 0
    is_staff: bool = False
    confidence: float = Field(..., ge=0.0, le=1.0)
    metadata: EventMetadata = Field(default_factory=EventMetadata)

    @field_validator("visitor_id")
    @classmethod
    def visitor_id_not_empty(cls, v):
        if not v.strip():
            raise ValueError("visitor_id cannot be empty")
        return v


class IngestRequest(BaseModel):
    events: list[Event] = Field(..., max_length=500)


class IngestResponse(BaseModel):
    accepted: int
    duplicates: int
    errors: int
    error_details: list[str] = []


class HealthStore(BaseModel):
    store_id: str
    last_event_time: Optional[datetime]
    status: Literal["OK", "STALE_FEED", "NO_DATA"]


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    stores: list[HealthStore]
    db_connected: bool

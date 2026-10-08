from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.services.events import EventType
from app.services.recommendations import AdSelection


class RecommendationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: int = Field(strict=True, gt=0, le=9223372036854775807)


class EventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recommendation_id: UUID


class RecommendationResponse(BaseModel):
    recommendation_id: UUID
    user_id: int
    created_at: datetime
    selection: AdSelection


class EventResponse(BaseModel):
    recommendation_id: UUID
    event_type: EventType
    user_id: int
    ad_id: int
    created_at: datetime
    simulated_revenue: Decimal


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail

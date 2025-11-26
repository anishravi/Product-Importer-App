from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional
from datetime import datetime


class WebhookBase(BaseModel):
    url: str = Field(..., description="Webhook URL")
    event_types: List[str] = Field(..., description="List of event types to subscribe to")
    enabled: bool = Field(True, description="Enable/disable webhook")


class WebhookCreate(WebhookBase):
    pass


class WebhookUpdate(BaseModel):
    url: Optional[str] = None
    event_types: Optional[List[str]] = None
    enabled: Optional[bool] = None


class WebhookResponse(WebhookBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WebhookTestResponse(BaseModel):
    success: bool
    status_code: Optional[int] = None
    response_time_ms: Optional[float] = None
    error: Optional[str] = None


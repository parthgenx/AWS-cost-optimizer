"""Transport schemas kept separate from domain models."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Response for lightweight platform health checks."""

    status: Literal["ok"]
    service: str
    environment: str
    version: str


class FindingApprovalResponse(BaseModel):
    """Public confirmation of a successful approval."""

    finding_id: str
    status: Literal["approved"]
    approved_by: str
    approved_at: datetime


class CleanupRequestResponse(BaseModel):
    """Confirmation that EventBridge accepted a cleanup request."""

    finding_id: str
    event_id: str
    status: Literal["requested"]

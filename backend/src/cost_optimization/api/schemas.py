"""Transport schemas kept separate from domain models."""

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Response for lightweight platform health checks."""

    status: Literal["ok"]
    service: str
    environment: str
    version: str

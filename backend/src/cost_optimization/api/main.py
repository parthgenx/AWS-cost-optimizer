"""FastAPI application factory and basic operational endpoints."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import RequestResponseEndpoint

from cost_optimization.api.schemas import HealthResponse
from cost_optimization.config import Settings, get_settings
from cost_optimization.observability.context import reset_correlation_id, set_correlation_id
from cost_optimization.observability.logging import configure_logging

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the HTTP application with explicitly supplied or env settings."""
    application_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        configure_logging(application_settings)
        logger.info("application_started", extra={"version": application_settings.version})
        yield
        logger.info("application_stopped")

    app = FastAPI(
        title="AWS Cost Optimization Automation System",
        version=application_settings.version,
        lifespan=lifespan,
    )
    app.state.settings = application_settings

    @app.middleware("http")
    async def add_correlation_id(request: Request, call_next: RequestResponseEndpoint) -> Response:
        incoming_id = request.headers.get("X-Correlation-ID")
        correlation_id = incoming_id if incoming_id and len(incoming_id) <= 128 else str(uuid4())
        token = set_correlation_id(correlation_id)
        try:
            response = await call_next(request)
            response.headers["X-Correlation-ID"] = correlation_id
            return response
        finally:
            reset_correlation_id(token)

    @app.get("/health", response_model=HealthResponse, tags=["Operations"])
    async def health() -> HealthResponse:
        logger.info("health_check_completed")
        return HealthResponse(
            status="ok",
            service=application_settings.service_name,
            environment=application_settings.environment,
            version=application_settings.version,
        )

    return app


app = create_app()

"""FastAPI application factory and basic operational endpoints."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, Response, status
from starlette.middleware.base import RequestResponseEndpoint

from cost_optimization.api.schemas import (
    CleanupRequestResponse,
    FindingApprovalResponse,
    HealthResponse,
)
from cost_optimization.application.services.approve_finding import (
    ApproveFinding,
    FindingNotFoundError,
)
from cost_optimization.application.services.request_cleanup import RequestCleanup
from cost_optimization.config import Settings, get_settings
from cost_optimization.infrastructure.aws.eventbridge_cleanup_requests import (
    EventBridgeCleanupRequestPublisher,
    create_eventbridge_client,
)
from cost_optimization.infrastructure.persistence.dynamodb import (
    DynamoDbFindingApprovalRepository,
    DynamoDbFindingRepository,
    get_dynamodb_client,
    get_dynamodb_table,
)
from cost_optimization.observability.context import reset_correlation_id, set_correlation_id
from cost_optimization.observability.logging import configure_logging

logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    *,
    approval_service: ApproveFinding | None = None,
    cleanup_request_service: RequestCleanup | None = None,
) -> FastAPI:
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
    app.state.approval_service = approval_service or _approval_service_from_settings(
        application_settings
    )
    app.state.cleanup_request_service = (
        cleanup_request_service or _cleanup_request_service_from_settings(application_settings)
    )

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

    @app.post(
        "/findings/{finding_id}/approval",
        response_model=FindingApprovalResponse,
        status_code=status.HTTP_200_OK,
        tags=["Findings"],
    )
    async def approve_finding(finding_id: str, request: Request) -> FindingApprovalResponse:
        """Approve an open finding using a trusted operator identity from the transport layer."""
        approved_by = request.headers.get("X-Operator-ID")
        if not approved_by:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="X-Operator-ID is required"
            )
        service = app.state.approval_service
        if service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Approval persistence is not configured",
            )
        try:
            finding = service.execute(
                finding_id=finding_id,
                approved_by=approved_by,
                approved_at=datetime.now(UTC),
            )
        except FindingNotFoundError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
        assert finding.approval is not None
        logger.info("finding_approved", extra={"finding_id": finding.finding_id})
        return FindingApprovalResponse(
            finding_id=finding.finding_id,
            status="approved",
            approved_by=finding.approval.approved_by,
            approved_at=finding.approval.approved_at,
        )

    @app.post(
        "/findings/{finding_id}/cleanup-requests",
        response_model=CleanupRequestResponse,
        status_code=status.HTTP_202_ACCEPTED,
        tags=["Findings"],
    )
    async def request_cleanup(finding_id: str, request: Request) -> CleanupRequestResponse:
        """Publish a separate EventBridge request; approval alone never starts deletion."""
        requested_by = request.headers.get("X-Operator-ID")
        if not requested_by:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="X-Operator-ID is required"
            )
        service = app.state.cleanup_request_service
        if service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Cleanup request publishing is not configured",
            )
        try:
            event_id = service.execute(finding_id=finding_id, requested_by=requested_by)
        except FindingNotFoundError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
        logger.info("cleanup_requested", extra={"finding_id": finding_id, "event_id": event_id})
        return CleanupRequestResponse(finding_id=finding_id, event_id=event_id, status="requested")

    return app


def _approval_service_from_settings(settings: Settings) -> ApproveFinding | None:
    """Wire approval dependencies only when the application is configured for persistence."""
    if not settings.findings_table_name or not settings.audit_events_table_name:
        return None
    findings_table_name, audit_events_table_name = settings.require_approval_configuration()
    return ApproveFinding(
        DynamoDbFindingRepository(get_dynamodb_table(findings_table_name)),
        DynamoDbFindingApprovalRepository(
            get_dynamodb_client(),
            findings_table_name=findings_table_name,
            audit_events_table_name=audit_events_table_name,
        ),
    )


def _cleanup_request_service_from_settings(settings: Settings) -> RequestCleanup | None:
    """Wire EventBridge publishing only when region and findings persistence are configured."""
    if not settings.aws_region or not settings.findings_table_name:
        return None
    return RequestCleanup(
        DynamoDbFindingRepository(get_dynamodb_table(settings.findings_table_name)),
        EventBridgeCleanupRequestPublisher(create_eventbridge_client(settings.aws_region)),
    )


app = create_app()

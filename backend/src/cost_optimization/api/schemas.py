"""Transport schemas kept separate from domain models."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from cost_optimization.application.services.read_dashboard import DashboardOverview
from cost_optimization.domain.findings import (
    Finding,
    FindingApproval,
    FindingPage,
    FindingSummary,
    ScanRun,
    ScanRunPage,
)
from cost_optimization.domain.models import FindingSeverity, FindingStatus, ResourceType


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


class MoneyResponse(BaseModel):
    """A non-billing cost estimate displayed by the dashboard."""

    amount: Decimal
    currency: str


class ResourceReferenceResponse(BaseModel):
    """The stable identity of a resource associated with a finding."""

    resource_type: ResourceType
    resource_id: str
    region: str
    account_id: str


class FindingApprovalDetailResponse(BaseModel):
    """Approval metadata shown with a detailed finding."""

    approved_by: str
    approved_at: datetime

    @classmethod
    def from_domain(cls, approval: FindingApproval) -> FindingApprovalDetailResponse:
        """Map the domain approval without exposing persistence representation."""
        return cls(approved_by=approval.approved_by, approved_at=approval.approved_at)


class FindingResponse(BaseModel):
    """Dashboard-safe representation of a durable finding and its rule evidence."""

    finding_id: str
    rule_id: str
    resource: ResourceReferenceResponse
    summary: str
    recommended_action: str
    severity: FindingSeverity
    status: FindingStatus
    estimated_monthly_savings: MoneyResponse | None
    evidence: dict[str, str]
    first_detected_at: datetime
    last_detected_at: datetime
    occurrence_count: int
    approval: FindingApprovalDetailResponse | None

    @classmethod
    def from_domain(cls, finding: Finding) -> FindingResponse:
        """Map a domain finding to the stable HTTP response contract."""
        savings = finding.estimated_monthly_savings
        return cls(
            finding_id=finding.finding_id,
            rule_id=finding.rule_id,
            resource=ResourceReferenceResponse(
                resource_type=finding.resource.resource_type,
                resource_id=finding.resource.resource_id,
                region=finding.resource.region,
                account_id=finding.resource.account_id,
            ),
            summary=finding.summary,
            recommended_action=finding.recommended_action,
            severity=finding.severity,
            status=finding.status,
            estimated_monthly_savings=(
                MoneyResponse(amount=savings.amount, currency=savings.currency) if savings else None
            ),
            evidence=finding.evidence,
            first_detected_at=finding.first_detected_at,
            last_detected_at=finding.last_detected_at,
            occurrence_count=finding.occurrence_count,
            approval=(
                FindingApprovalDetailResponse.from_domain(finding.approval)
                if finding.approval
                else None
            ),
        )


class FindingListResponse(BaseModel):
    """Cursor-paginated result set for the dashboard findings list."""

    items: list[FindingResponse]
    next_cursor: str | None

    @classmethod
    def from_domain(cls, page: FindingPage) -> FindingListResponse:
        """Map a domain page to an HTTP page."""
        return cls(
            items=[FindingResponse.from_domain(finding) for finding in page.items],
            next_cursor=page.next_cursor,
        )


class ScanRunResponse(BaseModel):
    """A compact scan execution record for operations screens."""

    scan_id: str
    scanner_name: str
    started_at: datetime
    completed_at: datetime | None
    status: Literal["running", "completed", "failed"]
    evaluated_resource_count: int | None
    finding_count: int | None
    failure_type: str | None

    @classmethod
    def from_domain(cls, scan_run: ScanRun) -> ScanRunResponse:
        """Map a domain scan record to its public response representation."""
        return cls(
            scan_id=scan_run.scan_id,
            scanner_name=scan_run.scanner_name,
            started_at=scan_run.started_at,
            completed_at=scan_run.completed_at,
            status=scan_run.status,  # type: ignore[arg-type]
            evaluated_resource_count=scan_run.evaluated_resource_count,
            finding_count=scan_run.finding_count,
            failure_type=scan_run.failure_type,
        )


class ScanRunListResponse(BaseModel):
    """Cursor-paginated result set for scan execution history."""

    items: list[ScanRunResponse]
    next_cursor: str | None

    @classmethod
    def from_domain(cls, page: ScanRunPage) -> ScanRunListResponse:
        """Map a domain page to an HTTP page."""
        return cls(
            items=[ScanRunResponse.from_domain(scan_run) for scan_run in page.items],
            next_cursor=page.next_cursor,
        )


class FindingSummaryResponse(BaseModel):
    """Open-finding totals with only rule-provided savings estimates."""

    finding_count: int
    findings_with_known_savings_count: int
    known_monthly_savings_by_currency: dict[str, MoneyResponse]

    @classmethod
    def from_domain(cls, summary: FindingSummary) -> FindingSummaryResponse:
        """Map explicit non-billing savings estimates."""
        return cls(
            finding_count=summary.finding_count,
            findings_with_known_savings_count=summary.findings_with_known_savings_count,
            known_monthly_savings_by_currency={
                currency: MoneyResponse(amount=money.amount, currency=money.currency)
                for currency, money in summary.known_monthly_savings_by_currency.items()
            },
        )


class DashboardOverviewResponse(BaseModel):
    """Read-only dashboard landing-page data."""

    open_findings: FindingSummaryResponse
    recent_scans: list[ScanRunResponse]

    @classmethod
    def from_domain(cls, overview: DashboardOverview) -> DashboardOverviewResponse:
        """Map the application overview to its HTTP contract."""
        return cls(
            open_findings=FindingSummaryResponse.from_domain(overview.open_findings),
            recent_scans=[
                ScanRunResponse.from_domain(scan_run) for scan_run in overview.recent_scans
            ],
        )

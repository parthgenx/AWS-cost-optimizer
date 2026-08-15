"""Application service for authenticated dashboard read operations."""

from __future__ import annotations

from pydantic import BaseModel, Field

from cost_optimization.domain.findings import (
    Finding,
    FindingPage,
    FindingSummary,
    ScanRun,
    ScanRunPage,
)
from cost_optimization.domain.models import FindingSeverity, FindingStatus, ResourceType
from cost_optimization.domain.ports import FindingReadRepository, ScanRunReadRepository


class DashboardOverview(BaseModel):
    """Dashboard data assembled from read-only repositories."""

    open_findings: FindingSummary
    recent_scans: list[ScanRun] = Field(default_factory=list)


class FindingNotFoundError(LookupError):
    """Raised when a requested durable finding does not exist."""


class DashboardReadService:
    """Coordinates dashboard reads while keeping API and DynamoDB concerns separate."""

    def __init__(
        self,
        findings: FindingReadRepository,
        scan_runs: ScanRunReadRepository,
    ) -> None:
        self._findings = findings
        self._scan_runs = scan_runs

    def get_overview(self) -> DashboardOverview:
        """Return the current open-finding summary and a compact scan activity feed."""
        recent_scans = self._scan_runs.list_recent(limit=5, cursor=None)
        return DashboardOverview(
            open_findings=self._findings.summarize_by_status(status=FindingStatus.OPEN),
            recent_scans=recent_scans.items,
        )

    def list_findings(
        self,
        *,
        status: FindingStatus,
        resource_type: ResourceType | None,
        severity: FindingSeverity | None,
        limit: int,
        cursor: str | None,
    ) -> FindingPage:
        """Return a filtered, paginated lifecycle view for the findings screen."""
        return self._findings.list_by_status(
            status=status,
            resource_type=resource_type,
            severity=severity,
            limit=limit,
            cursor=cursor,
        )

    def get_finding(self, finding_id: str) -> Finding:
        """Return detailed evidence for one finding or a stable application error."""
        finding = self._findings.get_by_id(finding_id)
        if finding is None:
            raise FindingNotFoundError(f"Finding {finding_id} was not found")
        return finding

    def list_scan_runs(self, *, limit: int, cursor: str | None) -> ScanRunPage:
        """Return paginated recent scan activity."""
        return self._scan_runs.list_recent(limit=limit, cursor=cursor)

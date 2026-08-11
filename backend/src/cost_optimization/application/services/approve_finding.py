"""Application workflow for a human approval of one finding."""

from __future__ import annotations

from datetime import datetime

from cost_optimization.domain.findings import AuditEvent, Finding
from cost_optimization.domain.ports import FindingApprovalRepository, FindingLookup


class FindingNotFoundError(LookupError):
    """Raised when an approval targets a finding that does not exist."""


class ApproveFinding:
    """Load, validate, and atomically persist a finding approval."""

    def __init__(self, findings: FindingLookup, approvals: FindingApprovalRepository) -> None:
        self._findings = findings
        self._approvals = approvals

    def execute(self, *, finding_id: str, approved_by: str, approved_at: datetime) -> Finding:
        """Approve one open finding and append its matching audit event."""
        finding = self._findings.get_by_id(finding_id)
        if finding is None:
            raise FindingNotFoundError(f"Finding {finding_id} was not found")

        approved_finding = finding.approve(approved_by=approved_by, approved_at=approved_at)
        audit_event = AuditEvent.finding_approved(approved_finding)
        self._approvals.approve(approved_finding, audit_event)
        return approved_finding

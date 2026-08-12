"""Application workflow for explicitly requesting cleanup of an approved finding."""

from __future__ import annotations

from cost_optimization.application.services.approve_finding import FindingNotFoundError
from cost_optimization.domain.models import FindingStatus
from cost_optimization.domain.ports import CleanupRequestPublisher, FindingLookup


class RequestCleanup:
    """Publish an idempotent cleanup request only for a currently approved finding."""

    def __init__(self, findings: FindingLookup, publisher: CleanupRequestPublisher) -> None:
        self._findings = findings
        self._publisher = publisher

    def execute(self, *, finding_id: str, requested_by: str) -> str:
        """Verify lifecycle state before placing a request on the event bus."""
        finding = self._findings.get_by_id(finding_id)
        if finding is None:
            raise FindingNotFoundError(f"Finding {finding_id} was not found")
        if finding.status is not FindingStatus.APPROVED:
            raise ValueError("Only approved findings can request cleanup")
        return self._publisher.publish(finding_id=finding_id, requested_by=requested_by)

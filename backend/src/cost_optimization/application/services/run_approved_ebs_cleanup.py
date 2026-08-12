"""Safety-gated cleanup workflow for an approved unattached EBS-volume finding."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from cost_optimization.domain.findings import AuditEvent, AuditEventType
from cost_optimization.domain.models import FindingStatus, ResourceType
from cost_optimization.domain.ports import (
    EbsVolumeDeletion,
    EbsVolumeLookup,
    FindingLifecycleRepository,
    FindingLookup,
)
from cost_optimization.domain.rules.unattached_ebs_volume import UnattachedEbsVolumeRule

_CLEANUP_ACTOR = "ebs-cleanup-worker"


@dataclass(frozen=True)
class CleanupExecutionResult:
    """Small, non-sensitive outcome summary returned by the cleanup worker."""

    finding_id: str
    outcome: str
    dry_run: bool


class RunApprovedEbsCleanup:
    """Revalidate and optionally remove one approved EBS-volume finding."""

    def __init__(
        self,
        findings: FindingLookup,
        lifecycle: FindingLifecycleRepository,
        volumes: EbsVolumeLookup,
        deletion: EbsVolumeDeletion,
        rule: UnattachedEbsVolumeRule,
    ) -> None:
        self._findings = findings
        self._lifecycle = lifecycle
        self._volumes = volumes
        self._deletion = deletion
        self._rule = rule

    def execute(
        self, *, finding_id: str, executed_at: datetime, dry_run: bool
    ) -> CleanupExecutionResult:
        """Run the guarded workflow; duplicate or stale events are harmless no-ops."""
        finding = self._findings.get_by_id(finding_id)
        if finding is None or finding.status is not FindingStatus.APPROVED:
            return CleanupExecutionResult(finding_id=finding_id, outcome="ignored", dry_run=dry_run)
        if finding.resource.resource_type is not ResourceType.EBS_VOLUME:
            return CleanupExecutionResult(finding_id=finding_id, outcome="ignored", dry_run=dry_run)

        volume = self._volumes.get_volume(finding.resource.resource_id)
        candidate = volume and self._rule.evaluate(volume, executed_at)
        if dry_run:
            event_type = (
                AuditEventType.CLEANUP_DRY_RUN_COMPLETED
                if candidate is not None
                else AuditEventType.CLEANUP_SKIPPED
            )
            event = AuditEvent.lifecycle_event(
                finding=finding,
                event_type=event_type,
                actor=_CLEANUP_ACTOR,
                occurred_at=executed_at,
                details={
                    "dry_run": "true",
                    "reason": "revalidation_passed" if candidate else "not_eligible",
                },
            )
            self._lifecycle.record_event(
                finding_id=finding.finding_id,
                expected_status=FindingStatus.APPROVED,
                audit_event=event,
            )
            return CleanupExecutionResult(
                finding_id=finding_id,
                outcome="dry_run_ready" if candidate is not None else "skipped",
                dry_run=True,
            )

        in_progress = finding.begin_cleanup()
        self._lifecycle.transition(
            finding=in_progress,
            expected_status=FindingStatus.APPROVED,
            audit_event=AuditEvent.lifecycle_event(
                finding=in_progress,
                event_type=AuditEventType.CLEANUP_STARTED,
                actor=_CLEANUP_ACTOR,
                occurred_at=executed_at,
                details={"dry_run": "false"},
            ),
        )
        if candidate is None:
            resolved = in_progress.resolve_externally()
            self._lifecycle.transition(
                finding=resolved,
                expected_status=FindingStatus.CLEANUP_IN_PROGRESS,
                audit_event=AuditEvent.lifecycle_event(
                    finding=resolved,
                    event_type=AuditEventType.CLEANUP_SKIPPED,
                    actor=_CLEANUP_ACTOR,
                    occurred_at=executed_at,
                    details={"dry_run": "false", "reason": "not_eligible"},
                ),
            )
            return CleanupExecutionResult(finding_id=finding_id, outcome="skipped", dry_run=False)

        try:
            self._deletion.delete_volume(finding.resource.resource_id)
        except Exception:
            failed = in_progress.fail_cleanup()
            self._lifecycle.transition(
                finding=failed,
                expected_status=FindingStatus.CLEANUP_IN_PROGRESS,
                audit_event=AuditEvent.lifecycle_event(
                    finding=failed,
                    event_type=AuditEventType.CLEANUP_FAILED,
                    actor=_CLEANUP_ACTOR,
                    occurred_at=executed_at,
                    details={"dry_run": "false"},
                ),
            )
            raise

        cleaned = in_progress.complete_cleanup()
        self._lifecycle.transition(
            finding=cleaned,
            expected_status=FindingStatus.CLEANUP_IN_PROGRESS,
            audit_event=AuditEvent.lifecycle_event(
                finding=cleaned,
                event_type=AuditEventType.CLEANUP_COMPLETED,
                actor=_CLEANUP_ACTOR,
                occurred_at=executed_at,
                details={"dry_run": "false"},
            ),
        )
        return CleanupExecutionResult(finding_id=finding_id, outcome="cleaned", dry_run=False)

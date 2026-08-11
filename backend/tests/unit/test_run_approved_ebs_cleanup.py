from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from cost_optimization.application.services.run_approved_ebs_cleanup import RunApprovedEbsCleanup
from cost_optimization.domain.findings import AuditEvent, Finding
from cost_optimization.domain.models import (
    EbsVolume,
    EbsVolumeState,
    FindingCandidate,
    FindingSeverity,
    FindingStatus,
    Money,
    ResourceReference,
    ResourceType,
)
from cost_optimization.domain.rules.unattached_ebs_volume import (
    UnattachedEbsVolumeRule,
    UnattachedEbsVolumeRuleConfig,
)


def test_dry_run_revalidates_but_never_deletes_a_volume() -> None:
    now = datetime(2026, 8, 12, tzinfo=UTC)
    finding = _approved_finding(now)
    lifecycle = FakeLifecycleRepository()
    deletion = FakeDeletion()
    workflow = _workflow(finding, lifecycle, _volume(), deletion)

    result = workflow.execute(finding_id=finding.finding_id, executed_at=now, dry_run=True)

    assert result.outcome == "dry_run_ready"
    assert deletion.deleted_volume_ids == []
    assert lifecycle.events == [(FindingStatus.APPROVED, "cleanup_dry_run_completed")]


def test_execute_deletes_only_after_revalidation_and_records_transitions() -> None:
    now = datetime(2026, 8, 12, tzinfo=UTC)
    finding = _approved_finding(now)
    lifecycle = FakeLifecycleRepository()
    deletion = FakeDeletion()
    workflow = _workflow(finding, lifecycle, _volume(), deletion)

    result = workflow.execute(finding_id=finding.finding_id, executed_at=now, dry_run=False)

    assert result.outcome == "cleaned"
    assert deletion.deleted_volume_ids == [finding.resource.resource_id]
    assert lifecycle.transitions == [
        (FindingStatus.APPROVED, FindingStatus.CLEANUP_IN_PROGRESS, "cleanup_started"),
        (FindingStatus.CLEANUP_IN_PROGRESS, FindingStatus.CLEANED, "cleanup_completed"),
    ]


def test_execute_resolves_without_deleting_when_revalidation_fails() -> None:
    now = datetime(2026, 8, 12, tzinfo=UTC)
    finding = _approved_finding(now)
    lifecycle = FakeLifecycleRepository()
    deletion = FakeDeletion()
    workflow = _workflow(finding, lifecycle, None, deletion)

    result = workflow.execute(finding_id=finding.finding_id, executed_at=now, dry_run=False)

    assert result.outcome == "skipped"
    assert deletion.deleted_volume_ids == []
    assert lifecycle.transitions[-1][:2] == (
        FindingStatus.CLEANUP_IN_PROGRESS,
        FindingStatus.RESOLVED_EXTERNALLY,
    )


def test_execute_records_cleanup_failure_when_volume_deletion_raises() -> None:
    now = datetime(2026, 8, 12, tzinfo=UTC)
    finding = _approved_finding(now)
    lifecycle = FakeLifecycleRepository()
    workflow = _workflow(finding, lifecycle, _volume(), FailingDeletion())

    with pytest.raises(RuntimeError, match="simulated"):
        workflow.execute(finding_id=finding.finding_id, executed_at=now, dry_run=False)

    assert lifecycle.transitions[-1] == (
        FindingStatus.CLEANUP_IN_PROGRESS,
        FindingStatus.CLEANUP_FAILED,
        "cleanup_failed",
    )


class FakeFindingLookup:
    def __init__(self, finding: Finding) -> None:
        self._finding = finding

    def get_by_id(self, finding_id: str) -> Finding | None:
        return self._finding if self._finding.finding_id == finding_id else None


class FakeLifecycleRepository:
    def __init__(self) -> None:
        self.transitions: list[tuple[FindingStatus, FindingStatus, str]] = []
        self.events: list[tuple[FindingStatus, str]] = []

    def transition(
        self, *, finding: Finding, expected_status: FindingStatus, audit_event: AuditEvent
    ) -> None:
        self.transitions.append((expected_status, finding.status, audit_event.event_type.value))

    def record_event(
        self, *, finding_id: str, expected_status: FindingStatus, audit_event: AuditEvent
    ) -> None:
        assert finding_id == audit_event.finding_id
        self.events.append((expected_status, audit_event.event_type.value))


class FakeVolumeLookup:
    def __init__(self, volume: EbsVolume | None) -> None:
        self._volume = volume

    def get_volume(self, volume_id: str) -> EbsVolume | None:
        assert volume_id == "vol-0123456789abcdef0"
        return self._volume


class FakeDeletion:
    def __init__(self) -> None:
        self.deleted_volume_ids: list[str] = []

    def delete_volume(self, volume_id: str) -> None:
        self.deleted_volume_ids.append(volume_id)


class FailingDeletion:
    def delete_volume(self, volume_id: str) -> None:
        assert volume_id == "vol-0123456789abcdef0"
        raise RuntimeError("simulated delete failure")


def _workflow(
    finding: Finding,
    lifecycle: FakeLifecycleRepository,
    volume: EbsVolume | None,
    deletion: FakeDeletion,
) -> RunApprovedEbsCleanup:
    return RunApprovedEbsCleanup(
        FakeFindingLookup(finding),
        lifecycle,
        FakeVolumeLookup(volume),
        deletion,
        UnattachedEbsVolumeRule(
            UnattachedEbsVolumeRuleConfig(
                minimum_volume_age_days=14,
                reference_gib_monthly_rate_usd=Decimal("0.08"),
            )
        ),
    )


def _approved_finding(now: datetime) -> Finding:
    return Finding.from_candidate(_candidate(), now).approve(
        approved_by="operator-123", approved_at=now
    )


def _candidate() -> FindingCandidate:
    return FindingCandidate(
        rule_id="unattached-ebs-volume",
        resource=_resource(),
        summary="Volume is currently unattached.",
        recommended_action="Review the volume.",
        severity=FindingSeverity.LOW,
        estimated_monthly_savings=Money(amount=Decimal("1.60"), currency="USD"),
        evidence={"state": "available"},
    )


def _volume() -> EbsVolume:
    return EbsVolume(
        resource=_resource(),
        state=EbsVolumeState.AVAILABLE,
        size_gib=20,
        created_at=datetime(2026, 7, 1, tzinfo=UTC),
        volume_type="gp3",
        tags={},
    )


def _resource() -> ResourceReference:
    return ResourceReference(
        resource_type=ResourceType.EBS_VOLUME,
        resource_id="vol-0123456789abcdef0",
        region="ap-south-1",
        account_id="123456789012",
    )

from __future__ import annotations

from datetime import UTC, datetime

from cost_optimization.domain.models import (
    EbsSnapshot,
    EbsSnapshotState,
    ResourceReference,
    ResourceType,
)
from cost_optimization.domain.rules.old_ebs_snapshot import (
    OldEbsSnapshotRuleConfig,
    OldManualEbsSnapshotRule,
)


def test_old_completed_manual_snapshot_creates_review_finding_without_a_cost_estimate() -> None:
    candidate = _rule().evaluate(_snapshot(), datetime(2026, 8, 12, tzinfo=UTC))

    assert candidate is not None
    assert candidate.rule_id == "old-manual-ebs-snapshot"
    assert candidate.estimated_monthly_savings is None
    assert "incremental" in candidate.evidence["estimate_note"]


def test_ami_excluded_or_recent_snapshot_is_not_flagged() -> None:
    now = datetime(2026, 8, 12, tzinfo=UTC)

    assert _rule().evaluate(_snapshot(description="Created by CreateImage(i-123)"), now) is None
    assert _rule().evaluate(_snapshot(tags={"cost-optimizer:exclude": "true"}), now) is None
    assert _rule().evaluate(_snapshot(started_at=datetime(2026, 8, 1, tzinfo=UTC)), now) is None


def _rule() -> OldManualEbsSnapshotRule:
    return OldManualEbsSnapshotRule(OldEbsSnapshotRuleConfig(minimum_snapshot_age_days=90))


def _snapshot(
    *,
    started_at: datetime = datetime(2026, 1, 1, tzinfo=UTC),
    description: str = "Manual recovery checkpoint",
    tags: dict[str, str] | None = None,
) -> EbsSnapshot:
    return EbsSnapshot(
        resource=ResourceReference(
            resource_type=ResourceType.EBS_SNAPSHOT,
            resource_id="snap-123",
            account_id="123456789012",
            region="ap-south-1",
        ),
        state=EbsSnapshotState.COMPLETED,
        started_at=started_at,
        volume_id="vol-123",
        volume_size_gib=100,
        description=description,
        tags=tags or {},
    )

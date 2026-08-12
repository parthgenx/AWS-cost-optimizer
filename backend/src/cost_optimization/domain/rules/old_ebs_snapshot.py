"""Conservative detection rule for old, completed, self-owned manual EBS snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from cost_optimization.domain.models import (
    EbsSnapshot,
    EbsSnapshotState,
    FindingCandidate,
    FindingSeverity,
)
from cost_optimization.domain.policies.resource_exclusion import is_excluded_from_optimization

RULE_ID = "old-manual-ebs-snapshot"
_AMI_SNAPSHOT_DESCRIPTION_PREFIX = "Created by CreateImage("


@dataclass(frozen=True)
class OldEbsSnapshotRuleConfig:
    """Age threshold used to surface snapshots for human retention review."""

    minimum_snapshot_age_days: int

    def __post_init__(self) -> None:
        if self.minimum_snapshot_age_days < 1:
            raise ValueError("minimum_snapshot_age_days must be at least 1")


class OldManualEbsSnapshotRule:
    """Flags old manual snapshots without claiming source-volume size is billable storage."""

    def __init__(self, config: OldEbsSnapshotRuleConfig) -> None:
        self._config = config

    def evaluate(self, snapshot: EbsSnapshot, evaluated_at: datetime) -> FindingCandidate | None:
        """Return a review candidate for eligible completed snapshots only."""
        if evaluated_at.tzinfo is None:
            raise ValueError("evaluated_at must be timezone-aware")
        if snapshot.state is not EbsSnapshotState.COMPLETED:
            return None
        if is_excluded_from_optimization(snapshot.tags):
            return None
        if snapshot.description.startswith(_AMI_SNAPSHOT_DESCRIPTION_PREFIX):
            return None
        age = evaluated_at.astimezone(UTC) - snapshot.started_at.astimezone(UTC)
        if age < timedelta(days=self._config.minimum_snapshot_age_days):
            return None

        return FindingCandidate(
            rule_id=RULE_ID,
            resource=snapshot.resource,
            summary=(
                f"EBS snapshot {snapshot.resource.resource_id} is a completed, non-AMI snapshot "
                f"at least {self._config.minimum_snapshot_age_days} days old."
            ),
            recommended_action=(
                "Review retention and recovery requirements before deleting this snapshot."
            ),
            severity=FindingSeverity.LOW,
            estimated_monthly_savings=None,
            evidence={
                "state": snapshot.state,
                "started_at": snapshot.started_at.astimezone(UTC).isoformat(),
                "volume_id": snapshot.volume_id,
                "volume_size_gib": str(snapshot.volume_size_gib),
                "storage_tier": snapshot.storage_tier,
                "minimum_snapshot_age_days": str(self._config.minimum_snapshot_age_days),
                "estimate_note": (
                    "Snapshot billing is based on incremental stored data, not volume_size_gib."
                ),
            },
        )

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from cost_optimization.application.services.detect_old_ebs_snapshots import DetectOldEbsSnapshots
from cost_optimization.application.services.detect_unassociated_elastic_ips import (
    DetectUnassociatedElasticIps,
)
from cost_optimization.domain.models import (
    EbsSnapshot,
    EbsSnapshotState,
    ElasticIpAddress,
    ResourceReference,
    ResourceType,
)
from cost_optimization.domain.rules.old_ebs_snapshot import (
    OldEbsSnapshotRuleConfig,
    OldManualEbsSnapshotRule,
)
from cost_optimization.domain.rules.unassociated_elastic_ip import (
    UnassociatedElasticIpRule,
    UnassociatedElasticIpRuleConfig,
)


def test_elastic_ip_detection_counts_resources_and_returns_rule_candidates() -> None:
    result = DetectUnassociatedElasticIps(
        FakeElasticIpDiscovery([_address(), _address(association_id="eipassoc-123")]),
        UnassociatedElasticIpRule(
            UnassociatedElasticIpRuleConfig(reference_monthly_rate_usd=Decimal("3.60"))
        ),
    ).execute()

    assert result.evaluated_resource_count == 2
    assert len(result.findings) == 1


def test_snapshot_detection_counts_resources_and_returns_rule_candidates() -> None:
    result = DetectOldEbsSnapshots(
        FakeSnapshotDiscovery([_snapshot()]),
        OldManualEbsSnapshotRule(OldEbsSnapshotRuleConfig(minimum_snapshot_age_days=90)),
    ).execute(datetime(2026, 8, 12, tzinfo=UTC))

    assert result.evaluated_resource_count == 1
    assert result.findings[0].resource.resource_id == "snap-123"


class FakeElasticIpDiscovery:
    def __init__(self, addresses: list[ElasticIpAddress]) -> None:
        self._addresses = addresses

    def list_addresses(self) -> list[ElasticIpAddress]:
        return self._addresses


class FakeSnapshotDiscovery:
    def __init__(self, snapshots: list[EbsSnapshot]) -> None:
        self._snapshots = snapshots

    def list_owned_snapshots(self) -> list[EbsSnapshot]:
        return self._snapshots


def _address(*, association_id: str | None = None) -> ElasticIpAddress:
    return ElasticIpAddress(
        resource=ResourceReference(
            resource_type=ResourceType.ELASTIC_IP,
            resource_id="eipalloc-123",
            account_id="123456789012",
            region="ap-south-1",
        ),
        allocation_id="eipalloc-123",
        public_ip="203.0.113.10",
        association_id=association_id,
    )


def _snapshot() -> EbsSnapshot:
    return EbsSnapshot(
        resource=ResourceReference(
            resource_type=ResourceType.EBS_SNAPSHOT,
            resource_id="snap-123",
            account_id="123456789012",
            region="ap-south-1",
        ),
        state=EbsSnapshotState.COMPLETED,
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
        volume_id="vol-123",
        volume_size_gib=100,
    )

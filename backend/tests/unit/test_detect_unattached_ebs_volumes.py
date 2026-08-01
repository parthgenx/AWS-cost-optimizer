from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from cost_optimization.application.services.detect_unattached_ebs_volumes import (
    DetectUnattachedEbsVolumes,
)
from cost_optimization.domain.models import (
    EbsVolume,
    EbsVolumeState,
    ResourceReference,
    ResourceType,
)
from cost_optimization.domain.rules.unattached_ebs_volume import (
    UnattachedEbsVolumeRule,
    UnattachedEbsVolumeRuleConfig,
)


def test_detection_use_case_returns_only_qualifying_findings() -> None:
    now = datetime(2026, 8, 1, tzinfo=UTC)
    discovery = FakeEbsVolumeDiscovery(
        [_volume("vol-old", now - timedelta(days=14)), _volume("vol-new", now)]
    )
    rule = UnattachedEbsVolumeRule(
        UnattachedEbsVolumeRuleConfig(
            minimum_volume_age_days=14,
            reference_gib_monthly_rate_usd=Decimal("0.08"),
        )
    )

    result = DetectUnattachedEbsVolumes(discovery, rule).execute(now)

    assert result.evaluated_volume_count == 2
    assert [finding.resource.resource_id for finding in result.findings] == ["vol-old"]


class FakeEbsVolumeDiscovery:
    def __init__(self, volumes: list[EbsVolume]) -> None:
        self._volumes = volumes

    def list_unattached_volumes(self) -> list[EbsVolume]:
        return self._volumes


def _volume(resource_id: str, created_at: datetime) -> EbsVolume:
    return EbsVolume(
        resource=ResourceReference(
            resource_type=ResourceType.EBS_VOLUME,
            resource_id=resource_id,
            region="ap-south-1",
            account_id="123456789012",
        ),
        state=EbsVolumeState.AVAILABLE,
        size_gib=20,
        created_at=created_at,
        volume_type="gp3",
    )

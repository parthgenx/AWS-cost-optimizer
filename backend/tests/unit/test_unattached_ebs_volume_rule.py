from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from cost_optimization.domain.models import (
    EbsVolume,
    EbsVolumeState,
    FindingSeverity,
    ResourceReference,
    ResourceType,
)
from cost_optimization.domain.rules.unattached_ebs_volume import (
    RULE_ID,
    EbsVolumeMonthlySavingsEstimator,
    UnattachedEbsVolumeRule,
    UnattachedEbsVolumeRuleConfig,
)

NOW = datetime(2026, 8, 1, tzinfo=UTC)


def test_rule_creates_finding_for_old_unattached_volume() -> None:
    rule = _rule()

    finding = rule.evaluate(_volume(age_days=14, size_gib=125), NOW)

    assert finding is not None
    assert finding.rule_id == RULE_ID
    assert finding.severity is FindingSeverity.MEDIUM
    assert finding.estimated_monthly_savings is not None
    assert finding.estimated_monthly_savings.amount == Decimal("10.00")
    assert finding.evidence["state"] == "available"


def test_rule_ignores_volume_before_minimum_volume_age() -> None:
    assert _rule().evaluate(_volume(age_days=13), NOW) is None


def test_rule_ignores_explicitly_excluded_volume() -> None:
    excluded_volume = _volume(tags={"cost-optimizer:exclude": "TRUE"})

    assert _rule().evaluate(excluded_volume, NOW) is None


def test_rule_ignores_attached_volume_defensively() -> None:
    attached_volume = _volume(state=EbsVolumeState.IN_USE)

    assert _rule().evaluate(attached_volume, NOW) is None


def test_rule_rejects_naive_evaluation_time() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        _rule().evaluate(_volume(), datetime(2026, 8, 1))


def test_savings_estimator_rounds_to_usd_cents() -> None:
    estimator = EbsVolumeMonthlySavingsEstimator(Decimal("0.081"))

    estimate = estimator.estimate(_volume(size_gib=3))

    assert estimate.amount == Decimal("0.24")
    assert estimate.currency == "USD"


def _rule() -> UnattachedEbsVolumeRule:
    return UnattachedEbsVolumeRule(
        UnattachedEbsVolumeRuleConfig(
            minimum_volume_age_days=14,
            reference_gib_monthly_rate_usd=Decimal("0.08"),
        )
    )


def _volume(
    *,
    age_days: int = 14,
    size_gib: int = 20,
    state: EbsVolumeState = EbsVolumeState.AVAILABLE,
    tags: dict[str, str] | None = None,
) -> EbsVolume:
    return EbsVolume(
        resource=ResourceReference(
            resource_type=ResourceType.EBS_VOLUME,
            resource_id="vol-0123456789abcdef0",
            region="ap-south-1",
            account_id="123456789012",
        ),
        state=state,
        size_gib=size_gib,
        created_at=NOW - timedelta(days=age_days),
        volume_type="gp3",
        tags=tags or {},
    )

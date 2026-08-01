"""Detection rule for old EBS volumes that are currently unattached."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from cost_optimization.domain.models import (
    EbsVolume,
    EbsVolumeState,
    FindingCandidate,
    FindingSeverity,
    Money,
)
from cost_optimization.domain.policies.resource_exclusion import is_excluded_from_optimization

RULE_ID = "unattached-ebs-volume"
_MONTHLY_CURRENCY = "USD"


@dataclass(frozen=True)
class UnattachedEbsVolumeRuleConfig:
    """Thresholds and price assumption used for unattached EBS evaluation."""

    minimum_volume_age_days: int
    reference_gib_monthly_rate_usd: Decimal

    def __post_init__(self) -> None:
        if self.minimum_volume_age_days < 1:
            raise ValueError("minimum_volume_age_days must be at least 1")
        if self.reference_gib_monthly_rate_usd <= Decimal("0"):
            raise ValueError("reference_gib_monthly_rate_usd must be positive")


class EbsVolumeMonthlySavingsEstimator:
    """Calculates a transparent estimate from volume size and configured rate."""

    def __init__(self, reference_gib_monthly_rate_usd: Decimal) -> None:
        if reference_gib_monthly_rate_usd <= Decimal("0"):
            raise ValueError("reference_gib_monthly_rate_usd must be positive")
        self._reference_gib_monthly_rate_usd = reference_gib_monthly_rate_usd

    def estimate(self, volume: EbsVolume) -> Money:
        """Return the volume-only monthly storage saving estimate in USD."""
        amount = Decimal(volume.size_gib) * self._reference_gib_monthly_rate_usd
        return Money(
            amount=amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            currency=_MONTHLY_CURRENCY,
        )


class UnattachedEbsVolumeRule:
    """Creates findings for qualifying volumes without performing any AWS calls."""

    def __init__(self, config: UnattachedEbsVolumeRuleConfig) -> None:
        self._config = config
        self._savings_estimator = EbsVolumeMonthlySavingsEstimator(
            config.reference_gib_monthly_rate_usd
        )

    def evaluate(self, volume: EbsVolume, evaluated_at: datetime) -> FindingCandidate | None:
        """Return a candidate only when the volume is safe to flag for review."""
        if evaluated_at.tzinfo is None:
            raise ValueError("evaluated_at must be timezone-aware")
        if volume.state is not EbsVolumeState.AVAILABLE:
            return None
        if is_excluded_from_optimization(volume.tags):
            return None

        volume_age = evaluated_at.astimezone(UTC) - volume.created_at.astimezone(UTC)
        if volume_age < timedelta(days=self._config.minimum_volume_age_days):
            return None

        savings = self._savings_estimator.estimate(volume)
        return FindingCandidate(
            rule_id=RULE_ID,
            resource=volume.resource,
            summary=(
                f"EBS volume {volume.resource.resource_id} is currently unattached and at least "
                f"{self._config.minimum_volume_age_days} days old."
            ),
            recommended_action=(
                "Review and approve deletion only if the volume is no longer needed."
            ),
            severity=_severity_for(savings),
            estimated_monthly_savings=savings,
            evidence={
                "state": volume.state,
                "size_gib": str(volume.size_gib),
                "created_at": volume.created_at.astimezone(UTC).isoformat(),
                "minimum_volume_age_days": str(self._config.minimum_volume_age_days),
                "reference_gib_monthly_rate_usd": str(self._config.reference_gib_monthly_rate_usd),
            },
        )


def _severity_for(savings: Money) -> FindingSeverity:
    """Assign a consistent savings-oriented severity for operator triage."""
    if savings.amount >= Decimal("100"):
        return FindingSeverity.CRITICAL
    if savings.amount >= Decimal("50"):
        return FindingSeverity.HIGH
    if savings.amount >= Decimal("10"):
        return FindingSeverity.MEDIUM
    return FindingSeverity.LOW

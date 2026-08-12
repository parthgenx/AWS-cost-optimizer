"""Lambda entry point for dry-run-first cleanup of an approved EBS finding."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Protocol

from cost_optimization.application.services.run_approved_ebs_cleanup import RunApprovedEbsCleanup
from cost_optimization.config import Settings, get_settings
from cost_optimization.domain.rules.unattached_ebs_volume import (
    UnattachedEbsVolumeRule,
    UnattachedEbsVolumeRuleConfig,
)
from cost_optimization.infrastructure.aws.ec2_volumes import (
    Boto3EbsVolumeDiscovery,
    create_ec2_client,
)
from cost_optimization.infrastructure.persistence.dynamodb import (
    DynamoDbFindingLifecycleRepository,
    DynamoDbFindingRepository,
    get_dynamodb_client,
    get_dynamodb_table,
)
from cost_optimization.observability.logging import configure_logging
from cost_optimization.workers.lambda_identity import account_id_from_lambda_arn

logger = logging.getLogger(__name__)


class LambdaContext(Protocol):
    """Minimal context surface needed to derive the Lambda account identity."""

    invoked_function_arn: str


def handler(event: Mapping[str, object], context: LambdaContext) -> dict[str, object]:
    """Execute a cleanup request; configuration can only make it more restrictive."""
    return run_cleanup(
        event, get_settings(), account_id_from_lambda_arn(context.invoked_function_arn)
    )


def run_cleanup(
    event: Mapping[str, object], settings: Settings, account_id: str
) -> dict[str, object]:
    """Compose the isolated cleanup workflow and return a minimal execution summary."""
    configure_logging(settings)
    finding_id = _finding_id_from_event(event)
    workflow = build_workflow(settings, account_id)
    effective_dry_run = settings.cleanup_dry_run or not settings.cleanup_execution_enabled
    result = workflow.execute(
        finding_id=finding_id,
        executed_at=datetime.now(UTC),
        dry_run=effective_dry_run,
    )
    logger.info(
        "ebs_cleanup_completed",
        extra={
            "finding_id": result.finding_id,
            "outcome": result.outcome,
            "dry_run": result.dry_run,
        },
    )
    return {"finding_id": result.finding_id, "outcome": result.outcome, "dry_run": result.dry_run}


def build_workflow(settings: Settings, account_id: str) -> RunApprovedEbsCleanup:
    """Wire AWS-only adapters into a cleanup workflow with separate credentials."""
    region, findings_table_name, audit_events_table_name = settings.require_cleanup_configuration()
    volumes = Boto3EbsVolumeDiscovery(
        create_ec2_client(region), account_id=account_id, region=region
    )
    return RunApprovedEbsCleanup(
        findings=DynamoDbFindingRepository(get_dynamodb_table(findings_table_name)),
        lifecycle=DynamoDbFindingLifecycleRepository(
            get_dynamodb_client(),
            findings_table_name=findings_table_name,
            audit_events_table_name=audit_events_table_name,
        ),
        volumes=volumes,
        deletion=volumes,
        rule=UnattachedEbsVolumeRule(
            UnattachedEbsVolumeRuleConfig(
                minimum_volume_age_days=settings.ebs_unattached_minimum_volume_age_days,
                reference_gib_monthly_rate_usd=settings.ebs_reference_gib_monthly_rate_usd,
            )
        ),
    )


def _finding_id_from_event(event: Mapping[str, object]) -> str:
    detail = event.get("detail", event)
    if not isinstance(detail, Mapping):
        raise ValueError("cleanup event detail must be an object")
    finding_id = detail.get("finding_id")
    if not isinstance(finding_id, str) or not finding_id:
        raise ValueError("cleanup event must contain a non-empty finding_id")
    return finding_id

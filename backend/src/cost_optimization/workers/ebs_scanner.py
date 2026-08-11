"""Lambda entry point for a manually invokable unattached-EBS scan."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Protocol

from botocore.exceptions import BotoCoreError, ClientError

from cost_optimization.application.services.detect_unattached_ebs_volumes import (
    DetectUnattachedEbsVolumes,
)
from cost_optimization.application.services.run_ebs_detection_scan import RunEbsDetectionScan
from cost_optimization.config import Settings, get_settings
from cost_optimization.domain.findings import ScanRun
from cost_optimization.domain.rules.unattached_ebs_volume import (
    UnattachedEbsVolumeRule,
    UnattachedEbsVolumeRuleConfig,
)
from cost_optimization.infrastructure.aws.ec2_volumes import (
    Boto3EbsVolumeDiscovery,
    create_ec2_client,
)
from cost_optimization.infrastructure.aws.sns_notifications import (
    SnsScanSummaryPublisher,
    create_sns_client,
)
from cost_optimization.infrastructure.persistence.dynamodb import (
    DynamoDbFindingRepository,
    DynamoDbScanRunRepository,
    get_dynamodb_table,
)
from cost_optimization.observability.logging import configure_logging
from cost_optimization.observability.metrics import (
    log_completed_scan_metrics,
    log_failed_scan_metric,
    log_notification_failure_metric,
)

logger = logging.getLogger(__name__)


class LambdaContext(Protocol):
    """Minimal Lambda context contract used by this handler."""

    invoked_function_arn: str


def handler(event: Mapping[str, object], context: LambdaContext) -> dict[str, object]:
    """Run a persisted EBS scan in response to a manual Lambda invocation."""
    del event  # Manual invocation accepts an empty event until scheduling is introduced.
    return run_scan(context, get_settings())


def run_scan(
    context: LambdaContext,
    settings: Settings,
    *,
    evaluated_at: datetime | None = None,
) -> dict[str, object]:
    """Compose and execute the EBS scan workflow with explicit dependencies."""
    configure_logging(settings)
    account_id = account_id_from_lambda_arn(context.invoked_function_arn)
    workflow = build_workflow(settings, account_id)
    try:
        completed_scan = workflow.execute(evaluated_at or datetime.now(UTC))
    except Exception:
        log_failed_scan_metric(
            scanner_name="unattached-ebs-volume", environment=settings.environment
        )
        raise
    log_completed_scan_metrics(completed_scan, environment=settings.environment)
    publish_findings_notification(completed_scan, settings)
    logger.info(
        "ebs_scan_completed",
        extra={
            "scan_id": completed_scan.scan_id,
            "evaluated_resource_count": completed_scan.evaluated_resource_count,
            "finding_count": completed_scan.finding_count,
        },
    )
    return {
        "scan_id": completed_scan.scan_id,
        "status": completed_scan.status,
        "evaluated_resource_count": completed_scan.evaluated_resource_count,
        "finding_count": completed_scan.finding_count,
    }


def publish_findings_notification(completed_scan: ScanRun, settings: Settings) -> None:
    """Notify operators only when a successful scan identifies actionable findings."""
    if not completed_scan.finding_count or not settings.scan_notifications_topic_arn:
        return
    if not settings.aws_region:
        raise RuntimeError("AWS_REGION is required when scan notifications are enabled")

    publisher = SnsScanSummaryPublisher(
        create_sns_client(settings.aws_region), settings.scan_notifications_topic_arn
    )
    try:
        publisher.publish(completed_scan, environment=settings.environment)
    except (BotoCoreError, ClientError):
        logger.exception(
            "scan_notification_publish_failed",
            extra={"scan_id": completed_scan.scan_id, "scanner_name": completed_scan.scanner_name},
        )
        log_notification_failure_metric(
            scanner_name=completed_scan.scanner_name,
            environment=settings.environment,
            scan_id=completed_scan.scan_id,
        )


def build_workflow(settings: Settings, account_id: str) -> RunEbsDetectionScan:
    """Wire AWS adapters into the application workflow at the Lambda boundary."""
    region, findings_table_name, scan_runs_table_name = settings.require_scanner_configuration()
    discovery = Boto3EbsVolumeDiscovery(
        create_ec2_client(region), account_id=account_id, region=region
    )
    rule = UnattachedEbsVolumeRule(
        UnattachedEbsVolumeRuleConfig(
            minimum_volume_age_days=settings.ebs_unattached_minimum_volume_age_days,
            reference_gib_monthly_rate_usd=settings.ebs_reference_gib_monthly_rate_usd,
        )
    )
    return RunEbsDetectionScan(
        detector=DetectUnattachedEbsVolumes(discovery, rule),
        findings=DynamoDbFindingRepository(get_dynamodb_table(findings_table_name)),
        scan_runs=DynamoDbScanRunRepository(get_dynamodb_table(scan_runs_table_name)),
    )


def account_id_from_lambda_arn(invoked_function_arn: str) -> str:
    """Extract and validate the account ID from the Lambda invocation ARN."""
    arn_parts = invoked_function_arn.split(":")
    if len(arn_parts) < 7 or arn_parts[2] != "lambda" or not arn_parts[4].isdigit():
        raise ValueError("invoked_function_arn must be a valid Lambda ARN")
    account_id = arn_parts[4]
    if len(account_id) != 12:
        raise ValueError("Lambda ARN must contain a 12-digit AWS account ID")
    return account_id

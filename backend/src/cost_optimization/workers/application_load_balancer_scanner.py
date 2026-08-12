"""Lambda entry point for persisted Application Load Balancer traffic recommendations."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Protocol

from cost_optimization.application.services.detect_inactive_application_load_balancers import (
    DetectInactiveApplicationLoadBalancers,
)
from cost_optimization.application.services.run_detection_scan import RunDetectionScan
from cost_optimization.config import Settings, get_settings
from cost_optimization.domain.findings import ScanRun
from cost_optimization.domain.rules.inactive_application_load_balancer import (
    InactiveApplicationLoadBalancerRule,
    InactiveApplicationLoadBalancerRuleConfig,
)
from cost_optimization.infrastructure.aws.application_load_balancers import (
    Boto3ApplicationLoadBalancerDiscovery,
    create_elbv2_client,
)
from cost_optimization.infrastructure.aws.cloudwatch_metrics import (
    Boto3CloudWatchMetricReader,
    create_cloudwatch_client,
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
)
from cost_optimization.workers.lambda_identity import account_id_from_lambda_arn
from cost_optimization.workers.scan_notifications import publish_findings_notification

logger = logging.getLogger(__name__)
_SCANNER_NAME = "no-request-application-load-balancer"


class LambdaContext(Protocol):
    """Minimal Lambda context contract used by this handler."""

    invoked_function_arn: str


def handler(event: Mapping[str, object], context: LambdaContext) -> dict[str, object]:
    """Run a persisted Application Load Balancer traffic scan in response to an invocation."""
    del event
    return run_scan(get_settings(), account_id_from_lambda_arn(context.invoked_function_arn))


def run_scan(
    settings: Settings, account_id: str, *, evaluated_at: datetime | None = None
) -> dict[str, object]:
    """Compose and execute the ALB recommendation workflow with explicit dependencies."""
    configure_logging(settings)
    workflow = build_workflow(settings, account_id)
    try:
        completed_scan = workflow.execute(evaluated_at or datetime.now(UTC))
    except Exception:
        log_failed_scan_metric(scanner_name=_SCANNER_NAME, environment=settings.environment)
        raise
    log_completed_scan_metrics(completed_scan, environment=settings.environment)
    publish_findings_notification(completed_scan, settings)
    logger.info(
        "application_load_balancer_scan_completed", extra={"scan_id": completed_scan.scan_id}
    )
    return _scan_summary(completed_scan)


def build_workflow(settings: Settings, account_id: str) -> RunDetectionScan:
    """Wire ELBv2 and CloudWatch readers into a read-only recommendation scan."""
    region, findings_table_name, scan_runs_table_name = settings.require_scanner_configuration()
    detector = DetectInactiveApplicationLoadBalancers(
        Boto3ApplicationLoadBalancerDiscovery(
            create_elbv2_client(region), account_id=account_id, region=region
        ),
        Boto3CloudWatchMetricReader(create_cloudwatch_client(region)),
        InactiveApplicationLoadBalancerRule(
            InactiveApplicationLoadBalancerRuleConfig(
                lookback_days=settings.utilization_lookback_days
            )
        ),
        lookback_days=settings.utilization_lookback_days,
    )
    return RunDetectionScan(
        scanner_name=_SCANNER_NAME,
        detector=detector.execute,
        findings=DynamoDbFindingRepository(get_dynamodb_table(findings_table_name)),
        scan_runs=DynamoDbScanRunRepository(get_dynamodb_table(scan_runs_table_name)),
    )


def _scan_summary(scan_run: ScanRun) -> dict[str, object]:
    return {
        "scan_id": scan_run.scan_id,
        "status": scan_run.status,
        "evaluated_resource_count": scan_run.evaluated_resource_count,
        "finding_count": scan_run.finding_count,
    }

"""Lambda entry point for persisted unassociated Elastic IP detection."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import UTC, datetime

from cost_optimization.application.services.detect_unassociated_elastic_ips import (
    DetectUnassociatedElasticIps,
)
from cost_optimization.application.services.run_detection_scan import (
    DetectionScanResult,
    RunDetectionScan,
)
from cost_optimization.config import Settings, get_settings
from cost_optimization.domain.findings import ScanRun
from cost_optimization.domain.rules.unassociated_elastic_ip import (
    UnassociatedElasticIpRule,
    UnassociatedElasticIpRuleConfig,
)
from cost_optimization.infrastructure.aws.ec2_elastic_ips import Boto3ElasticIpDiscovery
from cost_optimization.infrastructure.aws.ec2_volumes import create_ec2_client
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
_SCANNER_NAME = "unassociated-elastic-ip"


def handler(event: Mapping[str, object], context: object) -> dict[str, object]:
    """Run an Elastic IP scan in response to a manual Lambda invocation."""
    del event
    invoked_function_arn = getattr(context, "invoked_function_arn", "")
    return run_scan(get_settings(), account_id_from_lambda_arn(invoked_function_arn))


def run_scan(
    settings: Settings, account_id: str, *, evaluated_at: datetime | None = None
) -> dict[str, object]:
    """Compose and execute an isolated Elastic IP detection workflow."""
    configure_logging(settings)
    workflow = build_workflow(settings, account_id)
    try:
        completed_scan = workflow.execute(evaluated_at or datetime.now(UTC))
    except Exception:
        log_failed_scan_metric(scanner_name=_SCANNER_NAME, environment=settings.environment)
        raise
    log_completed_scan_metrics(completed_scan, environment=settings.environment)
    publish_findings_notification(completed_scan, settings)
    logger.info("elastic_ip_scan_completed", extra={"scan_id": completed_scan.scan_id})
    return _scan_summary(completed_scan)


def build_workflow(settings: Settings, account_id: str) -> RunDetectionScan:
    """Wire only Elastic IP read dependencies into the generic scan persistence workflow."""
    region, findings_table_name, scan_runs_table_name = settings.require_scanner_configuration()
    detector = DetectUnassociatedElasticIps(
        Boto3ElasticIpDiscovery(create_ec2_client(region), account_id=account_id, region=region),
        UnassociatedElasticIpRule(
            UnassociatedElasticIpRuleConfig(
                reference_monthly_rate_usd=settings.elastic_ip_reference_monthly_rate_usd
            )
        ),
    )

    def detect(_: datetime) -> DetectionScanResult:
        result = detector.execute()
        return DetectionScanResult(
            evaluated_resource_count=result.evaluated_resource_count, findings=result.findings
        )

    return RunDetectionScan(
        scanner_name=_SCANNER_NAME,
        detector=detect,
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

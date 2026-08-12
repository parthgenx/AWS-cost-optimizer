"""Best-effort finding-summary notifications shared by read-only scanners."""

from __future__ import annotations

import logging

from botocore.exceptions import BotoCoreError, ClientError

from cost_optimization.config import Settings
from cost_optimization.domain.findings import ScanRun
from cost_optimization.infrastructure.aws.sns_notifications import (
    SnsScanSummaryPublisher,
    create_sns_client,
)
from cost_optimization.observability.metrics import log_notification_failure_metric

logger = logging.getLogger(__name__)


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

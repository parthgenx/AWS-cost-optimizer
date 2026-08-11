"""CloudWatch Embedded Metric Format helpers for scanner operations."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from cost_optimization.domain.findings import ScanRun

logger = logging.getLogger(__name__)

METRIC_NAMESPACE = "AwsCostOptimizer"


def log_completed_scan_metrics(scan_run: ScanRun, *, environment: str) -> None:
    """Emit scan outcome counts as CloudWatch metrics through structured logs."""
    logger.info(
        "scan_metrics_recorded",
        extra={
            "_aws": _metric_directive(
                ["CompletedScans", "EvaluatedResources", "FindingsDetected"], environment
            ),
            "Environment": environment,
            "ScannerName": scan_run.scanner_name,
            "CompletedScans": 1,
            "EvaluatedResources": scan_run.evaluated_resource_count or 0,
            "FindingsDetected": scan_run.finding_count or 0,
            "scan_id": scan_run.scan_id,
        },
    )


def log_failed_scan_metric(*, scanner_name: str, environment: str) -> None:
    """Emit a failure count before the Lambda re-raises a scanner error."""
    logger.error(
        "scan_failure_metric_recorded",
        extra={
            "_aws": _metric_directive(["FailedScans"], environment),
            "Environment": environment,
            "ScannerName": scanner_name,
            "FailedScans": 1,
        },
    )


def log_notification_failure_metric(*, scanner_name: str, environment: str, scan_id: str) -> None:
    """Emit an operator-visible metric if SNS publication fails after a successful scan."""
    logger.error(
        "notification_failure_metric_recorded",
        extra={
            "_aws": _metric_directive(["NotificationPublishFailures"], environment),
            "Environment": environment,
            "ScannerName": scanner_name,
            "NotificationPublishFailures": 1,
            "scan_id": scan_id,
        },
    )


def _metric_directive(metric_names: list[str], environment: str) -> dict[str, object]:
    return {
        "Timestamp": int(datetime.now(UTC).timestamp() * 1000),
        "CloudWatchMetrics": [
            {
                "Namespace": METRIC_NAMESPACE,
                "Dimensions": [["Environment", "ScannerName"]],
                "Metrics": [{"Name": metric_name, "Unit": "Count"} for metric_name in metric_names],
            }
        ],
    }

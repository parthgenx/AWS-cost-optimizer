"""SNS adapter for notifying operators about completed cost-optimization scans."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Protocol, cast

import boto3
from botocore.config import Config

from cost_optimization.domain.findings import ScanRun


class SnsTopicClient(Protocol):
    """Minimal SNS client surface used by the notification adapter."""

    def publish(self, **kwargs: object) -> Mapping[str, object]:
        """Publish one message to an SNS topic."""


def create_sns_client(region: str) -> SnsTopicClient:
    """Create an SNS client with bounded standard retries."""
    return cast(
        SnsTopicClient,
        boto3.client(
            "sns",
            region_name=region,
            config=Config(retries={"mode": "standard", "max_attempts": 5}),
        ),
    )


class SnsScanSummaryPublisher:
    """Formats and publishes a compact scan summary to one SNS topic."""

    def __init__(self, client: SnsTopicClient, topic_arn: str) -> None:
        self._client = client
        self._topic_arn = topic_arn

    def publish(self, scan_run: ScanRun, *, environment: str) -> None:
        """Publish a completed scan summary; callers decide whether it is needed."""
        if scan_run.status != "completed":
            raise ValueError("Only completed scan runs can be published")
        if scan_run.completed_at is None:
            raise ValueError("Completed scan runs must have completed_at")

        finding_count = scan_run.finding_count or 0
        payload = {
            "environment": environment,
            "scanner_name": scan_run.scanner_name,
            "scan_id": scan_run.scan_id,
            "completed_at": scan_run.completed_at.isoformat(),
            "evaluated_resource_count": scan_run.evaluated_resource_count or 0,
            "finding_count": finding_count,
        }
        self._client.publish(
            TopicArn=self._topic_arn,
            Subject=f"[{environment}] {finding_count} AWS cost-optimization findings",
            Message=json.dumps(payload, separators=(",", ":"), sort_keys=True),
        )

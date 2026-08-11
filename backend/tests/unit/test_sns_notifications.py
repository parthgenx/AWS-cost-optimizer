from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from botocore.exceptions import ClientError

from cost_optimization.config import Environment, Settings
from cost_optimization.domain.findings import ScanRun
from cost_optimization.infrastructure.aws.sns_notifications import SnsScanSummaryPublisher
from cost_optimization.workers import ebs_scanner


def test_sns_scan_summary_publisher_formats_completed_scan() -> None:
    client = FakeSnsClient()
    scan_run = _completed_scan(finding_count=2)

    SnsScanSummaryPublisher(client, "arn:aws:sns:ap-south-1:123456789012:topic").publish(
        scan_run, environment="development"
    )

    request = client.requests[0]
    assert request["Subject"] == "[development] 2 AWS cost-optimization findings"
    assert json.loads(str(request["Message"])) == {
        "completed_at": "2026-08-09T00:00:00+00:00",
        "environment": "development",
        "evaluated_resource_count": 4,
        "finding_count": 2,
        "scan_id": "scan-123",
        "scanner_name": "unattached-ebs-volume",
    }


def test_sns_scan_summary_publisher_rejects_incomplete_scan() -> None:
    scan_run = ScanRun.start("unattached-ebs-volume", datetime(2026, 8, 9, tzinfo=UTC))

    with pytest.raises(ValueError, match="Only completed"):
        SnsScanSummaryPublisher(FakeSnsClient(), "topic").publish(
            scan_run, environment="development"
        )


def test_worker_skips_sns_for_scan_without_findings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ebs_scanner,
        "create_sns_client",
        lambda _: pytest.fail("SNS client must not be created for zero findings"),
    )

    ebs_scanner.publish_findings_notification(
        _completed_scan(finding_count=0), _notification_settings()
    )


def test_worker_logs_sns_publish_failure_without_rerunning_scan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FailingSnsClient()
    monkeypatch.setattr(ebs_scanner, "create_sns_client", lambda _: client)

    ebs_scanner.publish_findings_notification(
        _completed_scan(finding_count=1), _notification_settings()
    )

    assert client.publish_attempts == 1


class FakeSnsClient:
    def __init__(self) -> None:
        self.requests: list[dict[str, object]] = []

    def publish(self, **kwargs: object) -> dict[str, object]:
        self.requests.append(kwargs)
        return {"MessageId": "message-123"}


class FailingSnsClient:
    def __init__(self) -> None:
        self.publish_attempts = 0

    def publish(self, **_: object) -> dict[str, object]:
        self.publish_attempts += 1
        raise ClientError({"Error": {"Code": "InternalError", "Message": "simulated"}}, "Publish")


def _completed_scan(*, finding_count: int) -> ScanRun:
    return ScanRun(
        scan_id="scan-123",
        scanner_name="unattached-ebs-volume",
        started_at=datetime(2026, 8, 9, tzinfo=UTC),
        completed_at=datetime(2026, 8, 9, tzinfo=UTC),
        status="completed",
        evaluated_resource_count=4,
        finding_count=finding_count,
    )


def _notification_settings() -> Settings:
    return Settings(
        environment=Environment.DEVELOPMENT,
        aws_region="ap-south-1",
        findings_table_name="findings-table",
        scan_runs_table_name="scan-runs-table",
        scan_notifications_topic_arn="arn:aws:sns:ap-south-1:123456789012:notifications",
    )

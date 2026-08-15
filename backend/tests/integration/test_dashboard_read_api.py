from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from fastapi.testclient import TestClient

from cost_optimization.api.main import create_app
from cost_optimization.application.services.read_dashboard import DashboardReadService
from cost_optimization.config import Environment, Settings
from cost_optimization.domain.findings import (
    Finding,
    FindingPage,
    FindingSummary,
    ScanRun,
    ScanRunPage,
)
from cost_optimization.domain.models import (
    FindingCandidate,
    FindingSeverity,
    FindingStatus,
    Money,
    ResourceReference,
    ResourceType,
)


def test_dashboard_read_endpoints_require_an_authenticated_identity() -> None:
    app = _app_with_dashboard_data()

    with TestClient(app) as client:
        response = client.get("/dashboard/overview")

    assert response.status_code == 401
    assert response.json()["detail"] == "X-Operator-ID is required in trusted local mode"


def test_dashboard_read_endpoints_return_filtered_findings_details_and_scan_history() -> None:
    app = _app_with_dashboard_data()
    headers = {"X-Operator-ID": "dashboard-reader-123"}

    with TestClient(app) as client:
        overview = client.get("/dashboard/overview", headers=headers)
        findings = client.get(
            "/findings?status=open&resource_type=ebs_volume&severity=low&limit=10",
            headers=headers,
        )
        finding = client.get("/findings/finding-123", headers=headers)
        scans = client.get("/scan-runs?limit=10", headers=headers)

    assert overview.status_code == 200
    assert overview.json()["open_findings"] == {
        "finding_count": 1,
        "findings_with_known_savings_count": 1,
        "known_monthly_savings_by_currency": {"USD": {"amount": "1.60", "currency": "USD"}},
    }
    assert overview.json()["recent_scans"][0]["scanner_name"] == "unattached-ebs-volume"

    assert findings.status_code == 200
    assert findings.json()["items"][0]["finding_id"] == "finding-123"
    assert findings.json()["items"][0]["evidence"] == {"state": "available"}
    assert findings.json()["next_cursor"] is None

    assert finding.status_code == 200
    assert finding.json()["resource"]["resource_type"] == "ebs_volume"
    assert scans.status_code == 200
    assert scans.json()["items"][0]["status"] == "completed"


def test_dashboard_finding_detail_returns_not_found_for_a_missing_finding() -> None:
    app = _app_with_dashboard_data()

    with TestClient(app) as client:
        response = client.get(
            "/findings/missing", headers={"X-Operator-ID": "dashboard-reader-123"}
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Finding missing was not found"


class FakeDashboardFindingRepository:
    def __init__(self, finding: Finding) -> None:
        self._finding = finding

    def get_by_id(self, finding_id: str) -> Finding | None:
        return self._finding if finding_id == self._finding.finding_id else None

    def list_by_status(
        self,
        *,
        status: FindingStatus,
        resource_type: ResourceType | None,
        severity: FindingSeverity | None,
        limit: int,
        cursor: str | None,
    ) -> FindingPage:
        assert status is FindingStatus.OPEN
        assert resource_type is ResourceType.EBS_VOLUME
        assert severity is FindingSeverity.LOW
        assert limit == 10
        assert cursor is None
        return FindingPage(items=[self._finding])

    def summarize_by_status(self, *, status: FindingStatus) -> FindingSummary:
        assert status is FindingStatus.OPEN
        return FindingSummary(
            finding_count=1,
            findings_with_known_savings_count=1,
            known_monthly_savings_by_currency={
                "USD": Money(amount=Decimal("1.60"), currency="USD")
            },
        )


class FakeScanRunRepository:
    def __init__(self, scan_run: ScanRun) -> None:
        self._scan_run = scan_run

    def list_recent(self, *, limit: int, cursor: str | None) -> ScanRunPage:
        assert cursor is None
        assert limit in {5, 10}
        return ScanRunPage(items=[self._scan_run])


def _app_with_dashboard_data():
    finding = Finding.from_candidate(_candidate(), datetime(2026, 8, 12, tzinfo=UTC)).model_copy(
        update={"finding_id": "finding-123"}
    )
    scan_run = ScanRun(
        scan_id="scan-123",
        scanner_name="unattached-ebs-volume",
        started_at=datetime(2026, 8, 12, tzinfo=UTC),
        completed_at=datetime(2026, 8, 12, 0, 1, tzinfo=UTC),
        status="completed",
        evaluated_resource_count=1,
        finding_count=1,
    )
    return create_app(
        Settings(environment=Environment.TESTING),
        dashboard_read_service=DashboardReadService(
            FakeDashboardFindingRepository(finding), FakeScanRunRepository(scan_run)
        ),
    )


def _candidate() -> FindingCandidate:
    return FindingCandidate(
        rule_id="unattached-ebs-volume",
        resource=ResourceReference(
            resource_type=ResourceType.EBS_VOLUME,
            resource_id="vol-0123456789abcdef0",
            region="ap-south-1",
            account_id="123456789012",
        ),
        summary="Volume is currently unattached.",
        recommended_action="Review the volume.",
        severity=FindingSeverity.LOW,
        estimated_monthly_savings=Money(amount=Decimal("1.60"), currency="USD"),
        evidence={"state": "available"},
    )

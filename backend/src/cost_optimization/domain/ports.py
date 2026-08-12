"""Ports implemented by infrastructure adapters."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from cost_optimization.domain.findings import AuditEvent, Finding, ScanRun
from cost_optimization.domain.models import (
    EbsSnapshot,
    EbsVolume,
    ElasticIpAddress,
    FindingCandidate,
    FindingStatus,
)


class EbsVolumeDiscovery(Protocol):
    """Retrieves EBS volumes that could be evaluated by detection rules."""

    def list_unattached_volumes(self) -> list[EbsVolume]:
        """Return only currently unattached EBS volumes."""


class ElasticIpDiscovery(Protocol):
    """Retrieves Elastic IP addresses that could be evaluated by detection rules."""

    def list_addresses(self) -> list[ElasticIpAddress]:
        """Return Elastic IP addresses visible to the configured account and region."""


class EbsSnapshotDiscovery(Protocol):
    """Retrieves account-owned EBS snapshots that could be evaluated by detection rules."""

    def list_owned_snapshots(self) -> list[EbsSnapshot]:
        """Return EBS snapshots owned by the configured AWS account."""


class FindingRepository(Protocol):
    """Records an observed finding without exposing persistence details."""

    def record_detection(self, candidate: FindingCandidate, detected_at: datetime) -> Finding:
        """Create or refresh the durable finding for an observed candidate."""


class FindingLookup(Protocol):
    """Reads a durable finding by its stable identity."""

    def get_by_id(self, finding_id: str) -> Finding | None:
        """Return a finding when it exists, otherwise return None."""


class FindingApprovalRepository(Protocol):
    """Persists an approval and its audit record as one atomic operation."""

    def approve(self, finding: Finding, audit_event: AuditEvent) -> None:
        """Transition an open finding to approved and append its audit event."""


class FindingLifecycleRepository(Protocol):
    """Atomically records a guarded cleanup-state transition and audit evidence."""

    def transition(
        self,
        *,
        finding: Finding,
        expected_status: FindingStatus,
        audit_event: AuditEvent,
    ) -> None:
        """Persist the target status only if the current status matches the expectation."""

    def record_event(
        self,
        *,
        finding_id: str,
        expected_status: FindingStatus,
        audit_event: AuditEvent,
    ) -> None:
        """Append an event only while a finding remains in the expected state."""


class EbsVolumeLookup(Protocol):
    """Retrieves one EBS volume for live cleanup revalidation."""

    def get_volume(self, volume_id: str) -> EbsVolume | None:
        """Return the volume when it exists, otherwise return None."""


class EbsVolumeDeletion(Protocol):
    """Deletes one EBS volume after all safety checks have completed."""

    def delete_volume(self, volume_id: str) -> None:
        """Delete a volume by ID."""


class CleanupRequestPublisher(Protocol):
    """Publishes an explicit request for an approved cleanup execution."""

    def publish(self, *, finding_id: str, requested_by: str) -> str:
        """Publish a cleanup request and return its provider event identifier."""


class ScanRunRepository(Protocol):
    """Records execution-level scanner state for auditability and operations."""

    def create(self, scan_run: ScanRun) -> None:
        """Persist a newly started scan run."""

    def complete(
        self, scan_run: ScanRun, *, completed_at: datetime, evaluated_count: int, finding_count: int
    ) -> None:
        """Mark a running scan successful with its outcome counts."""

    def fail(self, scan_run: ScanRun, *, completed_at: datetime, failure_type: str) -> None:
        """Mark a running scan failed without persisting sensitive error details."""

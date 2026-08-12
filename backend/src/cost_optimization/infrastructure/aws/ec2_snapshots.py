"""boto3-backed, self-owned EBS snapshot discovery through the EC2 API."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from datetime import UTC, datetime
from typing import Protocol

from cost_optimization.domain.models import (
    EbsSnapshot,
    EbsSnapshotState,
    ResourceReference,
    ResourceType,
)


class SnapshotPaginator(Protocol):
    """Small protocol matching the paginator surface used by this adapter."""

    def paginate(self, **kwargs: object) -> Iterator[Mapping[str, object]]:
        """Yield paginated EC2 API result pages."""


class SnapshotClient(Protocol):
    """Small EC2 client surface required by the snapshot adapter."""

    def get_paginator(self, operation_name: str) -> SnapshotPaginator:
        """Return a paginator for the requested EC2 operation."""


class AwsSnapshotResponseFormatError(ValueError):
    """Raised when required EBS snapshot response fields are missing or malformed."""


class Boto3EbsSnapshotDiscovery:
    """Maps self-owned ``describe_snapshots`` results into domain snapshot models."""

    def __init__(self, client: SnapshotClient, *, account_id: str, region: str) -> None:
        self._client = client
        self._account_id = account_id
        self._region = region

    def list_owned_snapshots(self) -> list[EbsSnapshot]:
        """Retrieve only this account's completed snapshots through paginated API calls."""
        paginator = self._client.get_paginator("describe_snapshots")
        snapshots: list[EbsSnapshot] = []
        for page in paginator.paginate(
            OwnerIds=["self"], Filters=[{"Name": "status", "Values": ["completed"]}]
        ):
            for raw_snapshot in _required_list(page, "Snapshots"):
                snapshots.append(
                    self._to_domain_snapshot(_required_mapping(raw_snapshot, "snapshot"))
                )
        return snapshots

    def _to_domain_snapshot(self, raw_snapshot: Mapping[str, object]) -> EbsSnapshot:
        snapshot_id = _required_string(raw_snapshot, "SnapshotId")
        return EbsSnapshot(
            resource=ResourceReference(
                resource_type=ResourceType.EBS_SNAPSHOT,
                resource_id=snapshot_id,
                region=self._region,
                account_id=self._account_id,
            ),
            state=_required_snapshot_state(raw_snapshot),
            started_at=_required_datetime(raw_snapshot, "StartTime"),
            volume_id=_required_string(raw_snapshot, "VolumeId"),
            volume_size_gib=_required_positive_int(raw_snapshot, "VolumeSize"),
            description=_optional_string(raw_snapshot, "Description") or "",
            storage_tier=_optional_string(raw_snapshot, "StorageTier") or "standard",
            tags=_to_tag_mapping(raw_snapshot.get("Tags", [])),
        )


def _required_mapping(value: object, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise AwsSnapshotResponseFormatError(f"{field_name} must be an object")
    return value


def _required_list(page: Mapping[str, object], field_name: str) -> list[object]:
    value = page.get(field_name)
    if not isinstance(value, list):
        raise AwsSnapshotResponseFormatError(f"{field_name} must be a list")
    return value


def _required_string(values: Mapping[str, object], field_name: str) -> str:
    value = values.get(field_name)
    if not isinstance(value, str) or not value:
        raise AwsSnapshotResponseFormatError(f"{field_name} must be a non-empty string")
    return value


def _optional_string(values: Mapping[str, object], field_name: str) -> str | None:
    value = values.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise AwsSnapshotResponseFormatError(f"{field_name} must be a string when present")
    return value


def _required_positive_int(values: Mapping[str, object], field_name: str) -> int:
    value = values.get(field_name)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise AwsSnapshotResponseFormatError(f"{field_name} must be a positive integer")
    return value


def _required_datetime(values: Mapping[str, object], field_name: str) -> datetime:
    value = values.get(field_name)
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise AwsSnapshotResponseFormatError(f"{field_name} must be a timezone-aware datetime")
    return value.astimezone(UTC)


def _required_snapshot_state(values: Mapping[str, object]) -> EbsSnapshotState:
    try:
        return EbsSnapshotState(_required_string(values, "State"))
    except ValueError as error:
        raise AwsSnapshotResponseFormatError(
            "State is not a supported EBS snapshot state"
        ) from error


def _to_tag_mapping(value: object) -> dict[str, str]:
    if not isinstance(value, list):
        raise AwsSnapshotResponseFormatError("Tags must be a list")
    tags: dict[str, str] = {}
    for raw_tag in value:
        tag = _required_mapping(raw_tag, "tag")
        tags[_required_string(tag, "Key")] = _required_string(tag, "Value")
    return tags

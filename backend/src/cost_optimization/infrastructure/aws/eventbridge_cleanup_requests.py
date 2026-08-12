"""boto3 adapter that publishes explicit cleanup requests to EventBridge."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Protocol, cast

import boto3

_EVENT_SOURCE = "aws-cost-optimizer.cleanup"
_EVENT_DETAIL_TYPE = "CleanupRequested"


class EventBridgeClient(Protocol):
    """Minimal EventBridge client surface used by the cleanup-request publisher."""

    def put_events(self, **kwargs: object) -> Mapping[str, object]:
        """Publish one or more entries to EventBridge."""


def create_eventbridge_client(region: str) -> EventBridgeClient:
    """Create the EventBridge client at the infrastructure boundary."""
    return cast(EventBridgeClient, boto3.client("events", region_name=region))


class EventBridgeCleanupRequestPublisher:
    """Publishes one deterministic cleanup request for EventBridge routing."""

    def __init__(self, client: EventBridgeClient) -> None:
        self._client = client

    def publish(self, *, finding_id: str, requested_by: str) -> str:
        """Publish a request and reject partial EventBridge failures explicitly."""
        response = self._client.put_events(
            Entries=[
                {
                    "Source": _EVENT_SOURCE,
                    "DetailType": _EVENT_DETAIL_TYPE,
                    "Detail": json.dumps(
                        {"finding_id": finding_id, "requested_by": requested_by},
                        separators=(",", ":"),
                    ),
                }
            ]
        )
        if response.get("FailedEntryCount") != 0:
            raise RuntimeError("EventBridge rejected the cleanup request")
        entries = response.get("Entries")
        if (
            not isinstance(entries, list)
            or len(entries) != 1
            or not isinstance(entries[0], Mapping)
        ):
            raise ValueError("EventBridge cleanup request response was malformed")
        event_id = entries[0].get("EventId")
        if not isinstance(event_id, str) or not event_id:
            raise ValueError("EventBridge cleanup request did not return an event ID")
        return event_id

from __future__ import annotations

import json
import logging

from cost_optimization.config import Environment, Settings
from cost_optimization.observability.context import reset_correlation_id, set_correlation_id
from cost_optimization.observability.logging import JsonFormatter


def test_json_formatter_includes_context_and_extra_fields() -> None:
    settings = Settings(environment=Environment.TESTING)
    formatter = JsonFormatter(service_name=settings.service_name, environment=settings.environment)
    record = logging.makeLogRecord(
        {"name": "test", "levelno": logging.INFO, "msg": "scan completed", "scan_id": "scan-123"}
    )
    token = set_correlation_id("request-123")
    try:
        payload = json.loads(formatter.format(record))
    finally:
        reset_correlation_id(token)

    assert payload["message"] == "scan completed"
    assert payload["scan_id"] == "scan-123"
    assert payload["correlation_id"] == "request-123"
    assert payload["environment"] == "testing"

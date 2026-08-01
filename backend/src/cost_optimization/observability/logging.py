"""JSON logging configuration for API and worker processes."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from cost_optimization.config import Settings
from cost_optimization.observability.context import get_correlation_id


class JsonFormatter(logging.Formatter):
    """Render log records as one JSON object per line."""

    _reserved_fields = frozenset(logging.makeLogRecord({}).__dict__) | {
        "message",
        "asctime",
        "taskName",
    }

    def __init__(self, *, service_name: str, environment: str) -> None:
        super().__init__()
        self._service_name = service_name
        self._environment = environment

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "service": self._service_name,
            "environment": self._environment,
            "logger": record.name,
            "message": record.getMessage(),
        }
        correlation_id = get_correlation_id()
        if correlation_id is not None:
            payload["correlation_id"] = correlation_id
        payload.update(self._extra_fields(record))
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, separators=(",", ":"))

    def _extra_fields(self, record: logging.LogRecord) -> dict[str, Any]:
        return {
            key: value
            for key, value in record.__dict__.items()
            if key not in self._reserved_fields and not key.startswith("_")
        }


def configure_logging(settings: Settings) -> None:
    """Configure the application root logger without accumulating handlers."""
    root_logger = logging.getLogger()
    root_logger.setLevel(settings.log_level)

    for handler in list(root_logger.handlers):
        if handler.get_name() == "cost_optimizer_json":
            root_logger.removeHandler(handler)

    handler = logging.StreamHandler()
    handler.set_name("cost_optimizer_json")
    handler.setFormatter(
        JsonFormatter(service_name=settings.service_name, environment=settings.environment)
    )
    root_logger.addHandler(handler)

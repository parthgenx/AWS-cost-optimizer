"""Request-scoped context for structured log records."""

from __future__ import annotations

from contextvars import ContextVar, Token

_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def set_correlation_id(value: str) -> Token[str | None]:
    """Attach a correlation ID to the current async execution context."""
    return _correlation_id.set(value)


def reset_correlation_id(token: Token[str | None]) -> None:
    """Restore the previous correlation ID after a request completes."""
    _correlation_id.reset(token)


def get_correlation_id() -> str | None:
    """Read the correlation ID associated with the current execution."""
    return _correlation_id.get()

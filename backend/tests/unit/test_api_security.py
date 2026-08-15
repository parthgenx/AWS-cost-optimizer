from __future__ import annotations

from fastapi import HTTPException
from starlette.requests import Request

from cost_optimization.api.security import AuthenticatedIdentityResolver, OperatorIdentityResolver
from cost_optimization.config import Environment, OperatorIdentitySource, Settings


def test_jwt_identity_resolver_uses_verified_subject_for_operator_audit_identity() -> None:
    resolver = OperatorIdentityResolver(
        Settings(
            environment=Environment.PRODUCTION,
            operator_identity_source=OperatorIdentitySource.API_GATEWAY_JWT,
        )
    )
    request = _request_with_event(
        {
            "requestContext": {
                "authorizer": {
                    "jwt": {
                        "claims": {
                            "sub": "cognito-subject-123",
                            "cognito:groups": ["cost-optimizer-operators"],
                        }
                    }
                }
            }
        }
    )

    assert resolver.resolve(request) == "cognito-subject-123"


def test_authenticated_jwt_identity_resolver_allows_readers_without_operator_membership() -> None:
    resolver = AuthenticatedIdentityResolver(
        Settings(
            environment=Environment.PRODUCTION,
            operator_identity_source=OperatorIdentitySource.API_GATEWAY_JWT,
        )
    )
    request = _request_with_event(
        {"requestContext": {"authorizer": {"jwt": {"claims": {"sub": "cognito-reader-123"}}}}}
    )

    assert resolver.resolve(request) == "cognito-reader-123"


def test_jwt_identity_resolver_rejects_missing_operator_group() -> None:
    resolver = OperatorIdentityResolver(
        Settings(
            environment=Environment.PRODUCTION,
            operator_identity_source=OperatorIdentitySource.API_GATEWAY_JWT,
        )
    )
    request = _request_with_event(
        {"requestContext": {"authorizer": {"jwt": {"claims": {"sub": "cognito-subject-123"}}}}}
    )

    exception = _http_exception(lambda: resolver.resolve(request))

    assert exception.status_code == 403
    assert exception.detail == "Operator group membership is required"


def test_jwt_identity_resolver_rejects_a_spoofed_operator_header_without_gateway_claims() -> None:
    resolver = OperatorIdentityResolver(
        Settings(
            environment=Environment.PRODUCTION,
            operator_identity_source=OperatorIdentitySource.API_GATEWAY_JWT,
        )
    )
    request = Request(
        {
            "type": "http",
            "headers": [(b"x-operator-id", b"spoofed-operator")],
            "method": "POST",
            "path": "/findings/example/approval",
        }
    )

    exception = _http_exception(lambda: resolver.resolve(request))

    assert exception.status_code == 401


def test_production_api_rejects_caller_controlled_operator_headers() -> None:
    exception = _value_error(
        lambda: OperatorIdentityResolver(
            Settings(
                environment=Environment.PRODUCTION,
                operator_identity_source=OperatorIdentitySource.TRUSTED_HEADER,
            )
        )
    )

    assert "production API requires operator_identity_source=api_gateway_jwt" in str(exception)


def _request_with_event(event: dict[str, object]) -> Request:
    return Request(
        {
            "type": "http",
            "headers": [],
            "method": "POST",
            "path": "/findings/example/approval",
            "aws.event": event,
        }
    )


def _http_exception(operation: object) -> HTTPException:
    try:
        assert callable(operation)
        operation()
    except HTTPException as exception:
        return exception
    raise AssertionError("Expected HTTPException")


def _value_error(operation: object) -> ValueError:
    try:
        assert callable(operation)
        operation()
    except ValueError as exception:
        return exception
    raise AssertionError("Expected ValueError")

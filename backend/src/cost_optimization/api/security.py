"""Transport-level operator identity extraction for trusted and production API paths."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from fastapi import HTTPException, Request, status

from cost_optimization.config import Environment, OperatorIdentitySource, Settings


class OperatorIdentityResolver:
    """Extract the authenticated operator identity used by approval and cleanup audit events."""

    def __init__(self, settings: Settings) -> None:
        if (
            settings.environment is Environment.PRODUCTION
            and settings.operator_identity_source is not OperatorIdentitySource.API_GATEWAY_JWT
        ):
            raise ValueError("production API requires operator_identity_source=api_gateway_jwt")
        self._settings = settings

    def resolve(self, request: Request) -> str:
        """Return a verified subject, rejecting missing or unauthorized identities."""
        if self._settings.operator_identity_source is OperatorIdentitySource.API_GATEWAY_JWT:
            return self._resolve_api_gateway_jwt_subject(request)
        return self._resolve_trusted_header(request)

    def _resolve_trusted_header(self, request: Request) -> str:
        operator_id = request.headers.get("X-Operator-ID")
        if not operator_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="X-Operator-ID is required in trusted local mode",
            )
        return operator_id

    def _resolve_api_gateway_jwt_subject(self, request: Request) -> str:
        claims = _api_gateway_jwt_claims(request)
        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Verified JWT subject is required",
            )
        if self._settings.required_operator_group not in _groups_from_claims(claims):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Operator group membership is required",
            )
        return subject


def _api_gateway_jwt_claims(request: Request) -> Mapping[str, object]:
    """Return claims injected by API Gateway after its JWT authorizer validates the token."""
    event = request.scope.get("aws.event")
    if not isinstance(event, Mapping):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Verified API Gateway JWT claims are required",
        )
    request_context = event.get("requestContext")
    if not isinstance(request_context, Mapping):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Verified API Gateway JWT claims are required",
        )
    authorizer = request_context.get("authorizer")
    if not isinstance(authorizer, Mapping):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Verified API Gateway JWT claims are required",
        )
    jwt = authorizer.get("jwt")
    if not isinstance(jwt, Mapping):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Verified API Gateway JWT claims are required",
        )
    claims = jwt.get("claims")
    if not isinstance(claims, Mapping):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Verified API Gateway JWT claims are required",
        )
    return claims


def _groups_from_claims(claims: Mapping[str, object]) -> frozenset[str]:
    """Normalise Cognito's groups claim without trusting arbitrary scalar values."""
    raw_groups = claims.get("cognito:groups")
    if isinstance(raw_groups, str):
        return frozenset(group for group in raw_groups.split(",") if group)
    if isinstance(raw_groups, Sequence):
        return frozenset(group for group in raw_groups if isinstance(group, str) and group)
    return frozenset()

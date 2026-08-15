# ADR 0002: API Gateway JWT authorization with Cognito operators

## Status

Accepted.

## Context

The approval and cleanup-request endpoints change the lifecycle of a cost
finding. An `X-Operator-ID` header is useful for local tests but is controlled
by the caller and must never identify a production operator.

The API must authenticate a caller before FastAPI runs, preserve a stable actor
identity in the audit trail, and support a small trusted operator group without
adding a separate identity service.

## Decision

Deploy FastAPI behind an API Gateway HTTP API with a Cognito User Pool JWT
authorizer.

- The user pool permits administrator-created users only; public self-signup is
  disabled.
- The `cost-optimizer-operators` Cognito group represents operators permitted
  to approve findings and request cleanup.
- API Gateway validates token signature, issuer, audience, and expiry before
  invoking the Lambda integration.
- FastAPI extracts the API Gateway-provided JWT `sub` for authenticated
  dashboard reads. It additionally checks the Cognito group claim for approval
  and cleanup-request operations; that verified subject becomes the audit actor.
- The identity resolver rejects the trusted-header identity source in
  production. The header remains only for explicit local development and test
  settings.

AWS documents that HTTP API JWT authorizers validate JWT claims before
forwarding requests and expose validated claims to the Lambda integration.
[API Gateway JWT authorizers](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-jwt-authorizer.html)
Cognito includes group membership in access and ID tokens. [Cognito groups](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-pools-user-groups.html)

## Alternatives considered

### Trust a custom FastAPI header

This was retained only for local tests. It has no signature or caller binding,
so a public caller could impersonate any operator. It is unsuitable for a
production API.

### Verify Cognito tokens entirely in FastAPI

This would require key discovery, signature validation, issuer and audience
checks, cache rotation behaviour, and error handling in application code. API
Gateway already performs those checks at the edge, so duplicating them adds
security-sensitive code with little value.

### REST API with a Cognito authorizer

This is valid, but HTTP APIs provide the required JWT-authorizer capability
with a smaller configuration and operational footprint for this focused API.

### Custom Lambda authorizer

A custom authorizer is appropriate for non-standard policies or external
identity providers. Cognito provides managed identity, group claims, and JWT
rotation, so a custom authorizer would be unnecessary code and another Lambda
to operate.

## Consequences

The system gains an authenticated public entry point only after deployment.
Users must be explicitly provisioned. Only users placed in the required
operator group can approve findings or request cleanup. The API Lambda has
permissions only to read findings and scan runs, atomically record
approval/audit events, and publish an explicit cleanup request; it cannot
delete EBS volumes.

The next hardening increment adds monitoring and deployment roles. This
decision does not introduce public registration, a user-facing login page, or
a frontend.

## Operator provisioning after a deliberate deployment

Use an IAM principal authorised to administer the deployed user pool. Replace
the placeholder values with CloudFormation outputs and the intended operator:

```bash
aws cognito-idp admin-create-user \
  --user-pool-id <user-pool-id> \
  --username operator@example.com \
  --user-attributes Name=email,Value=operator@example.com Name=email_verified,Value=true \
  --region ap-south-1

aws cognito-idp admin-add-user-to-group \
  --user-pool-id <user-pool-id> \
  --username operator@example.com \
  --group-name cost-optimizer-operators \
  --region ap-south-1
```

Do not place the temporary password, access token, or refresh token in source
control, shell history shared with others, CI logs, or screenshots.

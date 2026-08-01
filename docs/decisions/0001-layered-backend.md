# ADR 0001: Use a pragmatic layered backend

## Status

Accepted.

## Decision

Use transport, application, domain, and infrastructure boundaries. Dependency
flow points inward: API routes and AWS adapters depend on domain contracts;
domain logic does not depend on FastAPI, boto3, or DynamoDB.

## Why

Detection rules and lifecycle policies need deterministic unit tests and must
remain understandable when new AWS resource types are added. Adapters make AWS
SDK behavior replaceable in tests and keep raw API responses out of business
logic.

## Alternatives considered

- **AWS SDK calls from route handlers:** fewer initial files but couples logic
  to transport and makes testing brittle.
- **Full domain-driven design with CQRS/event sourcing:** capable but excessive
  for this project's initial scale and obscures the core logic.

## Consequences

There are a few more small modules than a script-based implementation, but
every module has one clear responsibility. We will add interfaces only where a
real boundary exists, not for every class.

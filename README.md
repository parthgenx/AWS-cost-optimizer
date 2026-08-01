# AWS Cost Optimization Automation System

An approval-gated platform for discovering unused AWS resources, estimating
potential monthly savings, and coordinating safe cleanup operations.

The project is intentionally built in small, reviewable milestones. Its first
milestone establishes the backend engineering foundation; it does not yet query
AWS or perform resource cleanup.

## Repository layout

- `backend/` — FastAPI service, domain code, tests, and AWS infrastructure.
- `frontend/` — reserved for a future findings and approval dashboard.
- `docs/` — architecture, decision records, and operational documentation.
- `.github/` — continuous-integration workflows.

## Current milestone

Milestone 1 provides a typed FastAPI application, `GET /health`, centralized
configuration, JSON structured logging, domain primitives, Docker support, and
automated quality checks.

See [the architecture](docs/architecture.md) and
[the milestone plan](docs/milestones.md) before changing the design.

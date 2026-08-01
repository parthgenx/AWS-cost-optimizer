# AWS Cost Optimization Automation System

An approval-gated platform for discovering unused AWS resources, estimating
potential monthly savings, and coordinating safe cleanup operations.

The project is intentionally built in small, reviewable milestones. It now
includes a read-only EBS volume detection slice; it does not yet persist,
notify about, or clean up resources.

## Repository layout

- `backend/` — FastAPI service, domain code, tests, and AWS infrastructure.
- `frontend/` — reserved for a future findings and approval dashboard.
- `docs/` — architecture, decision records, and operational documentation.
- `.github/` — continuous-integration workflows.

## Current milestone

Milestone 2 adds paginated boto3 EBS discovery, a configurable unattached-volume
rule, a transparent reference-rate savings estimate, and universal resource
exclusions via `cost-optimizer:exclude=true`.

See [the architecture](docs/architecture.md) and
[the milestone plan](docs/milestones.md) before changing the design.

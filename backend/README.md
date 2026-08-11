# Backend service

## Prerequisites

Python 3.13 or 3.14. Production Lambda deployment will target Python 3.13;
Python 3.14 is supported for local development while it remains compatible with
the dependency set.

## Local development

```bash
python -m venv .venv
../.venv/bin/python -m pip install -e ".[dev]"
../.venv/bin/uvicorn cost_optimization.api.main:app --reload
```

The health endpoint is available at `http://localhost:8000/health`.

## EBS detection settings

The read-only unattached EBS volume rule is configured through environment
variables:

- `COST_OPTIMIZER_EBS_UNATTACHED_MINIMUM_VOLUME_AGE_DAYS` (default: `14`)
- `COST_OPTIMIZER_EBS_REFERENCE_GIB_MONTHLY_RATE_USD` (default: `0.08`)

The rate is a visible reference assumption, not a billing-grade price. Actual
EBS pricing varies by region and volume type; a future pricing adapter will
replace this configuration with AWS price data. Any resource tagged
`cost-optimizer:exclude=true` is excluded from findings.

AWS does not expose the time a volume was detached. The initial rule therefore
uses creation time as a minimum resource-age safety check; it does not claim
that the volume has been unattached for the whole threshold period.

## Quality checks

```bash
../.venv/bin/ruff check src tests
../.venv/bin/mypy src
../.venv/bin/pytest
```

## Dependency rationale

- `fastapi`: typed HTTP API framework and OpenAPI generation.
- `uvicorn`: ASGI server for local/container execution.
- `boto3`: future AWS SDK integration, kept out of domain logic.
- `pytest`, `httpx`: automated unit and API tests.
- `ruff`: formatting and linting in one fast tool.
- `mypy`: strict static type validation.
- `pytest-cov`: test coverage feedback in CI.

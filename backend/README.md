# Backend service

## Prerequisites

Python 3.13 or 3.14. Production Lambda deployment will target Python 3.13;
Python 3.14 is supported for local development while it remains compatible with
the dependency set.

## Local development

```bash
python -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/uvicorn cost_optimization.api.main:app --reload
```

The health endpoint is available at `http://localhost:8000/health`.

## Quality checks

```bash
.venv/bin/ruff check src tests
.venv/bin/mypy src
.venv/bin/pytest
```

## Dependency rationale

- `fastapi`: typed HTTP API framework and OpenAPI generation.
- `uvicorn`: ASGI server for local/container execution.
- `boto3`: future AWS SDK integration, kept out of domain logic.
- `pytest`, `httpx`: automated unit and API tests.
- `ruff`: formatting and linting in one fast tool.
- `mypy`: strict static type validation.
- `pytest-cov`: test coverage feedback in CI.

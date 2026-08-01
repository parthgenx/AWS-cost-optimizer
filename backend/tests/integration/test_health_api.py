from __future__ import annotations

from fastapi.testclient import TestClient

from cost_optimization.api.main import create_app
from cost_optimization.config import Environment, Settings


def test_health_endpoint_returns_operational_metadata() -> None:
    settings = Settings(
        service_name="test-service",
        environment=Environment.TESTING,
        version="test-version",
    )
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.get("/health", headers={"X-Correlation-ID": "correlation-123"})

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "test-service",
        "environment": "testing",
        "version": "test-version",
    }
    assert response.headers["X-Correlation-ID"] == "correlation-123"

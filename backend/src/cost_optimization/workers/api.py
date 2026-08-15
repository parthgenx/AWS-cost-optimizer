"""AWS Lambda adapter for the authenticated FastAPI application."""

from mangum import Mangum

from cost_optimization.api.main import app

handler = Mangum(app)

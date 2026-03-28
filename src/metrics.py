"""
Prometheus metrics for monitoring API performance.

Provides request metrics, system metrics, and custom application metrics.
"""

import time

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# System metrics
REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    ["method", "endpoint", "status_code"],
)

REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint"],
    buckets=(
        0.01,
        0.025,
        0.05,
        0.075,
        0.1,
        0.25,
        0.5,
        0.75,
        1.0,
        2.5,
        5.0,
        7.5,
        10.0,
        float("inf"),
    ),
)

# Custom application metrics
TASKS_ACTIVE = Gauge("plagiarism_tasks_active", "Number of active plagiarism tasks")
TASKS_QUEUED = Gauge("plagiarism_tasks_queued", "Number of queued tasks")
TASKS_COMPLETED = Counter("plagiarism_tasks_completed_total", "Total number of completed tasks")
TASKS_FAILED = Counter("plagiarism_tasks_failed_total", "Total number of failed tasks")

FILES_PROCESSED = Counter("plagiarism_files_processed_total", "Total number of files processed")
SIMILARITY_SCORE = Histogram(
    "plagiarism_similarity_score",
    "Distribution of similarity scores",
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 1.0],
)

REDIS_CONNECTED = Gauge("redis_connected", "Redis connection status (1=connected, 0=disconnected)")
RABBITMQ_CONNECTED = Gauge(
    "rabbitmq_connected", "RabbitMQ connection status (1=connected, 0=disconnected)"
)
DATABASE_CONNECTED = Gauge(
    "database_connected", "Database connection status (1=connected, 0=disconnected)"
)


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Middleware to collect HTTP request metrics."""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        response = await call_next(request)

        duration = time.time() - start_time

        # Record metrics
        REQUESTS_TOTAL.labels(
            method=request.method,
            endpoint=request.url.path,
            status_code=response.status_code,
        ).inc()

        REQUEST_DURATION.labels(
            method=request.method,
            endpoint=request.url.path,
        ).observe(duration)

        return response


def get_metrics_endpoint() -> Response:
    """
    Generate metrics endpoint response.

    Returns:
        Response with Prometheus metrics in text format
    """
    return Response(generate_latest(), media_type="text/plain; version=0.0.4")


def setup_metrics_app(app):
    """
    Add metrics middleware and endpoint to the app.

    Args:
        app: FastAPI application instance
    """
    # Add middleware
    app.add_middleware(PrometheusMiddleware)

    # Add metrics endpoint if configured
    from config import settings

    if settings.metrics_endpoint:

        @app.get(settings.metrics_endpoint, include_in_schema=False)
        async def metrics():
            return get_metrics_endpoint()

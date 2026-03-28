import logging
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from starlette.requests import Request as StarletteRequest

from clients.rabbit_client import RabbitMQ
from clients.redis_client import RedisClient
from clients.s3_client import S3Storage
from config import settings
from dependencies import get_redis_client
from exceptions.error_handler import add_exception_handler
from logging_config import configure_logging
from metrics import setup_metrics_app
from middleware.rate_limit import RateLimitMiddleware
from middleware.request_id import request_id_middleware as _request_id_middleware
from middleware.security_headers import SecurityHeadersMiddleware
from router import router as router_plagiarism
from startup.create_exchange import create_queues_and_exchanges
from websocket_manager import ConnectionManager

logger = logging.getLogger(__name__)


class CustomRequest(StarletteRequest):
    async def _get_form(
        self,
        *,
        max_files: int | float = float("inf"),
        max_fields: int | float = float("inf"),
        **kwargs,
    ):
        return await super()._get_form(max_files=max_files, max_fields=max_fields, **kwargs)


subpath = settings.subpath_normalized
subpath_for_routes = subpath.strip("/") if subpath else ""

# Conditionally hide docs in production
app_configs = {
    "title": settings.app_name,
    "description": "API for checking code plagiarism across multiple files using AST analysis and fingerprinting.",
    "version": settings.app_version,
    "contact": {"name": "API Support"},
    "request_class": CustomRequest,
}
if settings.environment == "production":
    app_configs["openapi_url"] = None

app = FastAPI(**app_configs)

# Setup Prometheus metrics (adds middleware and /metrics endpoint if configured)
setup_metrics_app(app)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

# Add rate limiting middleware (if enabled)
if settings.rate_limit_enabled:
    app.add_middleware(
        RateLimitMiddleware,
        rate_limit_requests=settings.rate_limit_requests,
        rate_limit_window=settings.rate_limit_window,
    )


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Attach a unique X-Request-ID to every request and response."""
    return await _request_id_middleware(request, call_next)


# Include API routers with subpath prefix
app.include_router(router_plagiarism, prefix=f"/{subpath_for_routes}")

add_exception_handler(app)

# Mount static files from React build
static_path = Path(__file__).parent / "frontend" / "dist"
logger.info("Static path: %s", static_path)
logger.info("Static path exists: %s", static_path.exists())
logger.info("Subpath: %s", subpath)

# Mount the assets directory to serve static files (JS, CSS)
if static_path.exists():
    assets_path = static_path / "assets"
    if assets_path.exists():
        app.mount("/assets", StaticFiles(directory=assets_path), name="assets")
        if subpath_for_routes:
            app.mount(
                f"/{subpath_for_routes}/assets",
                StaticFiles(directory=assets_path),
                name=f"assets_{subpath_for_routes}",
            )


@app.get("/favicon.png")
async def favicon():
    """Serve favicon"""
    favicon_path = static_path / "favicon.png"
    if favicon_path.exists():
        return FileResponse(favicon_path, media_type="image/png")
    return {"detail": "Not Found"}


if subpath_for_routes:

    @app.get(f"/{subpath_for_routes}/favicon.png")
    async def favicon_subpath():
        """Serve favicon"""
        favicon_path = static_path / "favicon.png"
        if favicon_path.exists():
            return FileResponse(favicon_path, media_type="image/png")
        return {"detail": "Not Found"}


@app.on_event("startup")
async def on_startup():
    # Configure structured logging first
    configure_logging(log_level=settings.log_level, log_format=settings.log_format)
    logger.info("Starting application", extra={"environment": settings.environment})

    await create_queues_and_exchanges()

    # Initialize S3 storage
    app.state.s3_storage = S3Storage()

    # Initialize Redis client
    redis_client = RedisClient()
    await redis_client.connect()
    app.state.redis_client = redis_client

    # Initialize RabbitMQ
    rabbitmq = RabbitMQ()
    await rabbitmq.connect()
    app.state.rabbitmq = rabbitmq

    # Initialize and start WebSocket manager
    ws_manager = ConnectionManager()
    await ws_manager.start()
    app.state.ws_manager = ws_manager


@app.on_event("shutdown")
async def on_shutdown():
    # Disconnect services
    await app.state.rabbitmq.disconnect()
    await app.state.redis_client.disconnect()
    await app.state.ws_manager.stop()


@app.get("/health")
async def health(request: Request, redis_client=Depends(get_redis_client)):
    """Health check endpoint — verifies all dependency connectivity."""
    from database import engine

    checks = {}
    overall_healthy = True

    # Database
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception:
        checks["db"] = "error"
        overall_healthy = False

    # Redis
    try:
        if redis_client:
            # Use async client with ping
            async_redis = request.app.state.redis_client.get_async_client()
            await async_redis.ping()
            checks["redis"] = "ok"
        else:
            checks["redis"] = "not_connected"
            overall_healthy = False
    except Exception:
        checks["redis"] = "error"
        overall_healthy = False

    # RabbitMQ
    try:
        rabbitmq = request.app.state.rabbitmq
        if rabbitmq.is_connected:
            checks["rmq"] = "ok"
        else:
            checks["rmq"] = "not_connected"
            overall_healthy = False
    except Exception:
        checks["rmq"] = "error"
        overall_healthy = False

    status_code = 200 if overall_healthy else 503
    from starlette.responses import JSONResponse

    return JSONResponse(
        status_code=status_code,
        content={"status": "healthy" if overall_healthy else "degraded", "checks": checks},
    )


@app.get("/version")
async def version():
    """API version endpoint"""
    return {"version": settings.app_version, "service": "plagiarism-api"}


@app.get("/")
async def root(request: Request):
    """Redirect to subpath"""
    if subpath_for_routes:
        return RedirectResponse(url=f"/{subpath_for_routes}/", status_code=302)
    return RedirectResponse(url="/dashboard", status_code=302)


if subpath_for_routes:

    @app.get(f"/{subpath_for_routes}/health")
    async def health_subpath():
        """Health check endpoint — delegates to /health."""
        return await health()

    @app.get(f"/{subpath_for_routes}/version")
    async def version_subpath():
        """API version endpoint"""
        return {"version": settings.app_version, "service": "plagiarism-api"}

    @app.get(f"/{subpath_for_routes}/")
    @app.get(f"/{subpath_for_routes}/{{full_path:path}}")
    async def serve_react_subpath(request: Request, full_path: str = ""):
        """Serve the React SPA for subpath routes"""
        if (
            full_path.startswith("api/")
            or full_path.startswith("assets/")
            or full_path.startswith("docs")
            or full_path.startswith("openapi")
            or full_path.startswith("plagiarism")
        ):
            return {"detail": "Not Found"}

        index_path = static_path / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        return {"message": "Plagiarism Detection API - Frontend not built"}


@app.get("/{full_path:path}")
async def serve_react(full_path: str, request: Request):
    """Serve the React SPA for all non-API routes"""
    if (
        full_path.startswith("api/")
        or full_path.startswith("assets/")
        or full_path.startswith("docs")
        or full_path.startswith("openapi")
        or full_path.startswith("plagiarism")
        or full_path.startswith("health")
        or full_path.startswith("version")
    ):
        return {"detail": "Not Found"}

    index_path = static_path / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "Plagiarism Detection API - Frontend not built"}

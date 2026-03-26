from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware

from api.plagiarism.router import router as router_plagiarism
from api.auth.router import router as router_auth
from exceptions.error_handler import add_exception_handler
from startup.create_exchange import create_queues_and_exchanges
from rabbit import connect, disconnect
from redis_client import connect_redis, disconnect_redis, get_redis_client
from config import settings
from websocket_manager import get_connection_manager


# Override Starlette's default 1000-file limit for multipart uploads
from starlette.requests import Request as StarletteRequest

class CustomRequest(StarletteRequest):
    async def _get_form(self, *, max_files: int | float = float("inf"), max_fields: int | float = float("inf"), **kwargs):
        return await super()._get_form(max_files=max_files, max_fields=max_fields, **kwargs)


subpath = settings.subpath_normalized
subpath_for_routes = subpath.strip("/") if subpath else ""

app = FastAPI(
    title="Plagiarism Detection API",
    request_class=CustomRequest,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers with subpath prefix
app.include_router(router_plagiarism, prefix=f"/{subpath_for_routes}")
app.include_router(router_auth, prefix=f"/{subpath_for_routes}")

add_exception_handler(app)

# Mount static files from React build
static_path = Path(__file__).parent / "frontend" / "dist"
print(f"Static path: {static_path}")
print(f"Static path exists: {static_path.exists()}")
print(f"Subpath: {subpath}")

# Mount the assets directory to serve static files (JS, CSS)
if static_path.exists():
    assets_path = static_path / "assets"
    if assets_path.exists():
        app.mount("/assets", StaticFiles(directory=assets_path), name="assets")
        if subpath_for_routes:
            app.mount(f"/{subpath_for_routes}/assets", StaticFiles(directory=assets_path), name=f"assets_{subpath_for_routes}")


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
    await create_queues_and_exchanges()
    await connect()
    await connect_redis()

    # Start WebSocket manager (creates its own Redis connection)
    manager = get_connection_manager()
    await manager.start()


@app.on_event("shutdown")
async def on_shutdown():
    await disconnect()
    await disconnect_redis()
    
    # Stop WebSocket manager
    manager = get_connection_manager()
    await manager.stop()


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get("/version")
async def version():
    """API version endpoint"""
    return {"version": "1.0.0", "service": "plagiarism-api"}


@app.get("/")
async def root(request: Request):
    """Redirect to subpath"""
    if subpath_for_routes:
        return RedirectResponse(url=f"/{subpath_for_routes}/", status_code=302)
    return RedirectResponse(url="/dashboard", status_code=302)


if subpath_for_routes:
    @app.get(f"/{subpath_for_routes}/health")
    async def health_subpath():
        """Health check endpoint"""
        return {"status": "healthy"}


    @app.get(f"/{subpath_for_routes}/version")
    async def version_subpath():
        """API version endpoint"""
        return {"version": "1.0.0", "service": "plagiarism-api"}


    @app.get(f"/{subpath_for_routes}/")
    @app.get(f"/{subpath_for_routes}/{{full_path:path}}")
    async def serve_react_subpath(request: Request, full_path: str = ""):
        """Serve the React SPA for subpath routes"""
        if full_path.startswith("api/") or full_path.startswith("assets/") or full_path.startswith("auth/") or full_path.startswith("docs") or full_path.startswith("openapi") or full_path.startswith("plagiarism"):
            return {"detail": "Not Found"}
        
        index_path = static_path / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        return {"message": "Plagiarism Detection API - Frontend not built"}


@app.get("/{full_path:path}")
async def serve_react(full_path: str, request: Request):
    """Serve the React SPA for all non-API routes"""
    if full_path.startswith("api/") or full_path.startswith("assets/") or full_path.startswith("auth/") or full_path.startswith("docs") or full_path.startswith("openapi") or full_path.startswith("plagiarism") or full_path.startswith("health") or full_path.startswith("version"):
        return {"detail": "Not Found"}
    
    index_path = static_path / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "Plagiarism Detection API - Frontend not built"}

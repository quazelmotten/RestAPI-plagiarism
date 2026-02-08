from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from plagiarism.router import router as router_plagiarism
from auth import router as router_auth
from exceptions.error_handler import add_exception_handler
from startup.create_exchange import create_queues_and_exchanges
from config import settings

app = FastAPI(title="Plagiarism Detection API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers first (so they take precedence)
app.include_router(router_plagiarism)
app.include_router(router_auth)

add_exception_handler(app)

# Mount static files from React build
static_path = Path(__file__).parent / "frontend" / "dist"
print(f"Static path: {static_path}")
print(f"Static path exists: {static_path.exists()}")

# Mount the assets directory to serve static files (JS, CSS)
if static_path.exists():
    assets_path = static_path / "assets"
    if assets_path.exists():
        app.mount("/assets", StaticFiles(directory=assets_path), name="assets")


@app.on_event("startup")
async def on_startup():
    await create_queues_and_exchanges()


@app.get("/")
async def root():
    """Serve the React app for the root route"""
    index_path = static_path / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "Plagiarism Detection API"}


# Serve React app for all other non-API routes (SPA fallback)
@app.get("/{full_path:path}")
async def serve_react(full_path: str):
    """Serve the React SPA for all non-API routes"""
    # Don't serve React app for API routes or static assets
    if full_path.startswith("api/") or full_path.startswith("plagiarism/") or full_path.startswith("assets/"):
        return {"detail": "Not Found"}
    
    index_path = static_path / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "Plagiarism Detection API - Frontend not built"}

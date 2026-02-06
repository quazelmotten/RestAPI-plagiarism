from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from plagiarism.router import router as router_plagiarism
from exceptions.error_handler import add_exception_handler
from startup.create_exchange import create_queues_and_exchanges

app = FastAPI(title="Plagiarism Detection API")

# Include API routers first (so they take precedence)
app.include_router(router_plagiarism)

add_exception_handler(app)

# Mount static files from React build
static_path = Path(__file__).parent / "frontend" / "dist"
if static_path.exists():
    # Mount the entire dist folder at root
    app.mount("/assets", StaticFiles(directory=static_path / "assets"), name="assets")


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
    # Don't serve React app for API routes
    if full_path.startswith("api/") or full_path.startswith("plagiarism/"):
        return {"detail": "Not Found"}
    
    index_path = static_path / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "Plagiarism Detection API - Frontend not built"}

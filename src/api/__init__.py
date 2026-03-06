from .plagiarism.router import router as plagiarism_router
from .auth.router import router as auth_router

__all__ = ["plagiarism_router", "auth_router"]

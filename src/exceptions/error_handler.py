import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from config import settings
from exceptions.exceptions import (
    ForbiddenError,
    NoAccessError,
    NotFoundError,
    PlagiarismValidationError,
)

logger = logging.getLogger(__name__)


def add_exception_handler(app: FastAPI) -> None:
    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, err: Exception):
        logger.error(
            "Unhandled exception on %s %s: %s", request.method, request.url.path, err, exc_info=True
        )
        if settings.is_development:
            detail = f"{type(err).__name__}: {err}"
        else:
            detail = "Internal server error"
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error_details": detail},
        )

    @app.exception_handler(NotFoundError)
    async def not_found_exception_handler(request: Request, err: NotFoundError):
        return JSONResponse(
            status_code=404,
            content={"status": "error", "error_details": err.message},
        )

    @app.exception_handler(PlagiarismValidationError)
    async def validation_exception_handler(request: Request, err: PlagiarismValidationError):
        return JSONResponse(
            status_code=400,
            content={"status": "error", "error_details": err.message},
        )

    @app.exception_handler(ForbiddenError)
    async def forbidden_exception_handler(request: Request, err: ForbiddenError):
        return JSONResponse(
            status_code=403,
            content={"status": "error", "error_details": err.message},
        )

    @app.exception_handler(NoAccessError)
    async def no_access_exception_handler(request: Request, err: NoAccessError):
        return JSONResponse(
            status_code=403,
            content={"status": "error", "error_details": err.message},
        )

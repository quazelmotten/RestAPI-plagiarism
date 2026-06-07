import logging

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

from exceptions.exceptions import (
    ConflictError,
    ForbiddenError,
    NoAccessError,
    NotFoundError,
    PlagiarismValidationError,
)

logger = logging.getLogger(__name__)


def add_exception_handler(app: FastAPI) -> None:
    @app.exception_handler(ValueError)
    async def value_error_exception_handler(request: Request, err: ValueError):
        logger.error(
            "Value error on %s %s: %s", request.method, request.url.path, err, exc_info=True
        )
        return JSONResponse(
            status_code=422,
            content={"status": "error", "error_details": str(err)},
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, err: Exception):
        logger.error(
            "Unhandled exception on %s %s: %s", request.method, request.url.path, err, exc_info=True
        )
        # Never expose internal error details to client
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error_details": "Internal server error"},
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

    @app.exception_handler(ConflictError)
    async def conflict_exception_handler(request: Request, err: ConflictError):
        return JSONResponse(
            status_code=409,
            content={"status": "error", "error_details": err.message},
        )

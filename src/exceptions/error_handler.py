from fastapi import FastAPI
from starlette.responses import JSONResponse

from exceptions.exceptions import NotFoundError


def add_exception_handler(app: FastAPI) -> None:
    @app.exception_handler(Exception)
    async def validation_exception_handler(request, err):
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error_details": f"{type(err).__name__}: {str(err)}",
            },
        )

    @app.exception_handler(NotFoundError)
    async def validation_exception_handler(request, err):
        return JSONResponse(
            status_code=404,
            content={
                "status": "error",
                "error_details": str(err),
            },
        )

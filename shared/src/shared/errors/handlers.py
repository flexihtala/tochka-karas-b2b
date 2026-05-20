"""FastAPI exception handlers для AppError + RequestValidationError."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from shared.errors.base import AppError, ErrorCode


async def _app_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    return JSONResponse(status_code=exc.status_code, content=exc.to_payload())


async def _validation_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    return JSONResponse(
        status_code=400,
        content={
            'error': {
                'code': str(ErrorCode.INVALID_REQUEST),
                'message': 'Validation failed',
                'details': {'errors': exc.errors()},
            }
        },
    )


def setup_error_handlers(app: FastAPI) -> None:
    """Регистрирует унифицированные handlers ошибок для FastAPI-приложения."""
    app.add_exception_handler(AppError, _app_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)

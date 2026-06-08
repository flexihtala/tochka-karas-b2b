from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from shared.errors.base import AppError as SharedAppError


class AppError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int,
        details: dict[str, Any] | None = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details: dict[str, Any] = details or {}


async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    body: dict[str, Any] = {'code': exc.code, 'message': exc.message}
    if exc.details:
        body['details'] = exc.details
    return JSONResponse(status_code=exc.status_code, content=body)


async def shared_app_error_handler(_: Request, exc: SharedAppError) -> JSONResponse:
    """Преобразует ошибки из shared/auth_lib (ForbiddenError, UnauthorizedError, ...) в плоский формат b2b."""
    return JSONResponse(
        status_code=exc.status_code,
        content={'code': str(exc.code), 'message': exc.message},
    )


async def validation_error_handler(_: Request, __: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={'code': 'INVALID_REQUEST', 'message': 'Невалидное тело запроса'},
    )


def setup_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(SharedAppError, shared_app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int):
        self.code = code
        self.message = message
        self.status_code = status_code


async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={'code': exc.code, 'message': exc.message},
    )


async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    message = 'Невалидное тело запроса'
    errors = exc.errors()
    if errors:
        first_error = errors[0]
        loc = first_error.get('loc', ())
        if len(loc) >= 2 and loc[0] == 'body':
            field = loc[1]
            error_type = first_error.get('type')
            if error_type == 'missing':
                message = f'{field} is required'
            else:
                message = str(first_error.get('msg', message))

    return JSONResponse(
        status_code=400,
        content={'code': 'INVALID_REQUEST', 'message': message},
    )


def setup_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)

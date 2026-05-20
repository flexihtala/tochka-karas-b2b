"""Базовый класс ошибок и формат ответа.

Все доменные ошибки наследуют AppError. Handlers конвертируют их в
HTTP-ответ единого формата:
    {"error": {"code": "INVALID_REQUEST", "message": "...", "details": {...}}}
"""

from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    """Канонические коды ошибок NeoMarket. Расширяется доменами при необходимости."""

    INVALID_REQUEST = 'INVALID_REQUEST'
    UNAUTHORIZED = 'UNAUTHORIZED'
    FORBIDDEN = 'FORBIDDEN'
    NOT_FOUND = 'NOT_FOUND'
    CONFLICT = 'CONFLICT'
    UNPROCESSABLE = 'UNPROCESSABLE'
    INTERNAL = 'INTERNAL'
    SERVICE_UNAVAILABLE = 'SERVICE_UNAVAILABLE'

    # Доменные коды (расширяется в use-cases)
    HARD_BLOCKED = 'HARD_BLOCKED'
    RESERVE_FAILED = 'RESERVE_FAILED'
    CANCEL_NOT_ALLOWED = 'CANCEL_NOT_ALLOWED'
    DUPLICATE = 'DUPLICATE'


class AppError(Exception):
    """Базовая ошибка домена. Все use-case ошибки наследуют этот класс.

    Атрибуты:
        code: код ошибки (ErrorCode или строка).
        message: человекочитаемое сообщение для клиента.
        status_code: HTTP-статус для ответа.
        details: произвольные дополнительные данные (опц.).
    """

    code: str = ErrorCode.INTERNAL
    status_code: int = 500
    message: str = 'Internal server error'

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message or self.message)
        if message is not None:
            self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        self.details: dict[str, Any] = details or {}

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {'code': str(self.code), 'message': self.message}
        if self.details:
            payload['details'] = self.details
        return {'error': payload}


# --- Стандартные подклассы для частых случаев ---


class InvalidRequestError(AppError):
    code = ErrorCode.INVALID_REQUEST
    status_code = 400
    message = 'Invalid request'


class UnauthorizedError(AppError):
    code = ErrorCode.UNAUTHORIZED
    status_code = 401
    message = 'Unauthorized'


class ForbiddenError(AppError):
    code = ErrorCode.FORBIDDEN
    status_code = 403
    message = 'Forbidden'


class NotFoundError(AppError):
    code = ErrorCode.NOT_FOUND
    status_code = 404
    message = 'Not found'


class ConflictError(AppError):
    code = ErrorCode.CONFLICT
    status_code = 409
    message = 'Conflict'

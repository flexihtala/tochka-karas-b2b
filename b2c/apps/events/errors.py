"""Доменные ошибки обработчика входящих B2B-событий."""

from apps.errors import AppError


class EventsError(AppError):
    pass


class UnsupportedEventTypeError(EventsError):
    """Пришёл event с типом вне поддерживаемого enum."""

    def __init__(self, message: str = 'Неподдерживаемый тип события'):
        super().__init__('INVALID_REQUEST', message, 400)

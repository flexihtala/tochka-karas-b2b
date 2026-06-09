from apps.errors import AppError


class EventError(AppError):
    pass


class EventInvalidRequestError(EventError):
    def __init__(self, message: str = 'Невалидное тело события'):
        super().__init__('INVALID_REQUEST', message, 400)


class EventProductNotFoundError(EventError):
    def __init__(self, message: str = 'Товар не найден'):
        super().__init__('NOT_FOUND', message, 404)


class BlockedReasonRequiredError(EventInvalidRequestError):
    def __init__(self, message: str = 'blocking_reason_id обязателен при event_type=BLOCKED'):
        super().__init__(message)

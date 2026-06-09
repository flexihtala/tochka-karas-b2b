from apps.errors import AppError


class BlockingReasonError(AppError):
    pass


class BlockingReasonNotFoundError(BlockingReasonError):
    def __init__(self, message: str = 'Причина блокировки не найдена'):
        super().__init__('BLOCKING_REASON_NOT_FOUND', message, 404)


class BlockingReasonAlreadyExistsError(BlockingReasonError):
    """409 — конфликт по уникальному name. Спека рекомендует, чтобы name был уникальным
    в рамках справочника."""

    def __init__(self, message: str = 'Причина с таким названием уже существует'):
        super().__init__('BLOCKING_REASON_ALREADY_EXISTS', message, 409)

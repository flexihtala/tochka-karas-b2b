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


class BlockingReasonReferencedError(BlockingReasonError):
    """409 — на причину ссылается карточка модерации (tickets.blocking_reason_id).

    DoD US-MOD-06 (referenced_reason_cannot_be_deleted): удаление такой причины запрещено.
    Скрыть её из справочника можно явной деактивацией — PATCH {is_active: false}.
    """

    def __init__(
        self,
        message: str = (
            'Причина используется тикетами модерации и не может быть удалена; '
            'деактивируйте её явно через PATCH {"is_active": false}'
        ),
    ):
        super().__init__('BLOCKING_REASON_REFERENCED', message, 409)

from apps.errors import AppError


class TicketError(AppError):
    pass


class TicketNotFoundError(TicketError):
    def __init__(self, message: str = 'Тикет не найден'):
        super().__init__('TICKET_NOT_FOUND', message, 404)


class TicketWrongStatusError(TicketError):
    """409 — тикет не в ожидаемом статусе (например, approve при PENDING)."""

    def __init__(self, message: str = 'Тикет в неподходящем статусе для этой операции'):
        super().__init__('TICKET_WRONG_STATUS', message, 409)


class TicketNotAssignedError(TicketError):
    """409 — тикет принадлежит другому модератору (block/release; spec moderation.yaml: 409)."""

    def __init__(self, message: str = 'Тикет назначен другому модератору'):
        super().__init__('TICKET_NOT_ASSIGNED', message, 409)


class TicketTerminalError(TicketError):
    """403 — тикет в терминальном статусе HARD_BLOCKED, любые мутации запрещены.

    US-MOD-05 (canon moderation-flows.md#hard-block, «Необратимость»): HARD_BLOCKED —
    терминальный статус. approve/block/release над таким тикетом отклоняются с 403
    (а не generic 409): продавец не может исправить, модератор не может пере-решить.
    """

    def __init__(self, message: str = 'Тикет в терминальном статусе HARD_BLOCKED, операция запрещена'):
        super().__init__('TICKET_TERMINAL', message, 403)


class TicketNotOwnerError(TicketError):
    """403 — approve чужой карточки.

    Отдельная ошибка от TicketNotAssignedError (409): канон approve-product (шаг 5)
    и DoD US-MOD-03 требуют для approve именно 403, тогда как спека block/release — 409.
    """

    def __init__(self, message: str = 'Эта карточка модерации закреплена за другим модератором'):
        super().__init__('TICKET_NOT_OWNER', message, 403)


class TicketNoSkusError(TicketError):
    """409 — у товара нет SKU, одобрить нельзя.

    Прекондишн approve (canon moderation-flows.md#approve-product, шаг 6): перед
    переводом в APPROVED проверяем у B2B, что товар всё ещё содержит хотя бы один SKU.
    """

    def __init__(self, message: str = 'Product has no SKUs, cannot approve'):
        super().__init__('PRODUCT_HAS_NO_SKUS', message, 409)


class B2BUnavailableError(TicketError):
    """503 — B2B сервис временно недоступен (5xx/timeout при проверке SKU).

    Поднимается B2B-клиентом при сетевом сбое/5xx. Статус тикета остаётся IN_REVIEW —
    модератор повторяет approve позже (canon moderation-flows.md#approve-product, шаг 10).
    """

    def __init__(self, message: str = 'Сервис B2B временно недоступен, попробуйте позже'):
        super().__init__('B2B_UNAVAILABLE', message, 503)

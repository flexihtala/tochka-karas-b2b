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
    """403 — approve/block чужой карточки.

    Отдельная ошибка от TicketNotAssignedError (409): канон approve-product (шаг 5)
    и канон MOD-4 soft-block (шаг 5, «Если moderator_id != текущий модератор → 403
    Forbidden (Not assigned to you)») требуют именно 403. Release остаётся на 409
    (TicketNotAssignedError) по спеке moderation.yaml.
    """

    def __init__(self, message: str = 'Эта карточка модерации закреплена за другим модератором'):
        super().__init__('TICKET_NOT_OWNER', message, 403)


class UnknownBlockingReasonError(TicketError):
    """400 — причина блокировки не найдена или неактивна (block-путь).

    Канон MOD-4 (шаг 7): «Если не найдена → 400 Bad Request (Blocking reason not found)».
    Отдельная от BlockingReasonNotFoundError (404 в CRUD справочника причин): в block-пути
    blocking_reason_id приходит в ТЕЛЕ запроса, поэтому неизвестный ID — некорректный
    запрос (400), а не отсутствие ресурса по URL (404).
    """

    def __init__(self, message: str = 'Blocking reason not found'):
        super().__init__('BLOCKING_REASON_NOT_FOUND', message, 400)


class InvalidFieldNameError(TicketError):
    """400 — field_reports[].field_name вне допустимого enum (канон MOD-4).

    Допустимые значения (apps.tickets.enums.FieldReportName): title, description,
    product_images, category, sku_name, sku_image, sku_price.
    """

    def __init__(self, message: str = 'Недопустимое значение field_name в field_reports'):
        super().__init__('INVALID_FIELD_NAME', message, 400)


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

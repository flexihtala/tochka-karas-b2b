from uuid import UUID

from apps.errors import AppError


class EventError(AppError):
    pass


class DuplicateEventError(EventError):
    """409 — событие с таким idempotency_key уже обработано (или обрабатывается).

    Спека: идемпотентность по idempotency_key (TTL 24h), дубликат → 409 без
    каких-либо побочных эффектов. Ключ фиксируется в processed_events ДО мутаций
    тикетов (UNIQUE(sender_service, idempotency_key) — арбитр гонки), поэтому
    повтор/out-of-order ретрай не может создать второй тикет.
    """

    def __init__(self, idempotency_key: UUID):
        super().__init__('DUPLICATE_EVENT', f'Событие с idempotency_key={idempotency_key} уже обработано', 409)


class TicketNotFoundForEditError(EventError):
    """404 — PRODUCT_EDITED пришёл, но активного тикета для товара нет.

    Канон moderation-flows.md (Edge Case 2): EDITED предполагает, что товар уже на
    модерации. Если активной записи нет (товар не заводился / уже архивирован) —
    редактировать нечего, отвечаем 404.
    """

    def __init__(self, message: str = 'Активный тикет для редактируемого товара не найден'):
        super().__init__('TICKET_NOT_FOUND', message, 404)


class UnsupportedEventTypeError(EventError):
    """400 — защита use-case от события, не покрытого бизнес-логикой.

    Pydantic уже валидирует event_type по enum, но use-case дополнительно защищается
    (например, PRODUCT_CREATED без обязательного seller_id).
    """

    def __init__(self, event_type: str):
        super().__init__('UNSUPPORTED_EVENT_TYPE', f'Неподдерживаемый тип события: {event_type}', 400)

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
    """409 — тикет назначен другому модератору."""

    def __init__(self, message: str = 'Тикет назначен другому модератору'):
        super().__init__('TICKET_NOT_ASSIGNED', message, 409)


class QueueEmptyError(TicketError):
    """404 при пустой очереди (спека возвращает 204, но мы маппим через стандартный AppError-механизм
    в 404 с понятным кодом; роутер при необходимости переопределит на 204.)."""

    def __init__(self, message: str = 'Очередь пуста'):
        super().__init__('QUEUE_EMPTY', message, 404)

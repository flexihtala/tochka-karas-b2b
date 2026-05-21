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

from apps.errors import AppError


class EventError(AppError):
    pass


class TicketNotFoundForEditError(EventError):
    def __init__(self, message: str = 'Тикет для редактирования не найден'):
        super().__init__('TICKET_NOT_FOUND', message, 404)


class UnsupportedEventTypeError(EventError):
    def __init__(self, event_type: str):
        super().__init__('UNSUPPORTED_EVENT_TYPE', f'Неподдерживаемый тип события: {event_type}', 400)

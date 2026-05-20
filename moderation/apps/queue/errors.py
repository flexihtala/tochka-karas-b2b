from apps.errors import AppError


class QueueError(AppError):
    pass


class QueueEmptyError(QueueError):
    """404 — нет PENDING-тикетов для claim'а.

    Спека описывает 204, но мы оставляем 404 с понятным кодом для единообразия —
    клиент видит code='QUEUE_EMPTY' и обрабатывает однозначно.
    """

    def __init__(self, message: str = 'Очередь пуста — нет тикетов для модерации'):
        super().__init__('QUEUE_EMPTY', message, 404)

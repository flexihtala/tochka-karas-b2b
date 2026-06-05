"""Доменные ошибки orders.

Все ошибки наследуются от apps.errors.AppError и перехватываются
глобальным error-handler'ом в плоский формат {code, message, ...}.
"""

from typing import Any

from apps.errors import AppError


class OrderError(AppError):
    pass


class OrderNotFoundError(OrderError):
    """404 — заказ не найден ИЛИ принадлежит другому пользователю.

    По канону (b2c-orders-flows.md, IDOR prevention) чужой заказ маскируется
    под 404, чтобы не раскрывать существование чужих ресурсов.
    """

    def __init__(self, message: str = 'Заказ не найден'):
        super().__init__('ORDER_NOT_FOUND', message, 404)


class ReserveFailedError(OrderError):
    """409 RESERVE_FAILED — B2B не смог зарезервировать (хотя бы один SKU).

    failed_items проксируется без трансформации из ответа B2B.
    """

    def __init__(
        self,
        failed_items: list[dict[str, Any]],
        message: str = 'Не удалось зарезервировать товары',
    ):
        super().__init__('RESERVE_FAILED', message, 409, extra={'failed_items': failed_items})
        self.failed_items = failed_items


class B2BUnavailableError(OrderError):
    """503 — B2B сервис временно недоступен.

    Поднимается use-case'ом при 5xx/timeout от B2B. Контракт API сохраняем
    единый: покупатель видит "сервис товаров временно недоступен".
    """

    def __init__(self, message: str = 'Сервис товаров временно недоступен, попробуйте позже'):
        super().__init__('B2B_UNAVAILABLE', message, 503)


class CancelNotAllowedError(OrderError):
    """409 CANCEL_NOT_ALLOWED — заказ нельзя отменить из текущего статуса.

    Канон: отмена допустима только из CREATED/PAID.
    """

    def __init__(self, current_status: str):
        super().__init__(
            'CANCEL_NOT_ALLOWED',
            f'Отмена невозможна: заказ в статусе {current_status}',
            409,
            extra={'current_status': current_status},
        )
        self.current_status = current_status

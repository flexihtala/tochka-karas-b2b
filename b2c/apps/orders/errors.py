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


class CartInvalidError(OrderError):
    """422 — корзина невалидна для чекаута.

    Spec (b2c openapi.yaml): POST /api/v1/orders 422 → CartValidationResponse.
    Поднимается, когда корзина пуста, товар/SKU недоступен, active_quantity <
    quantity, либо переданный items_snapshot расходится с актуальной корзиной.
    `issues` проксируется в details (формат CartValidationIssue: {sku_id, type,
    message, old_value?, new_value?}).
    """

    def __init__(
        self,
        issues: list[dict[str, Any]],
        message: str = 'Корзина невалидна',
    ):
        super().__init__('CART_INVALID', message, 422, extra={'details': {'issues': issues}})
        self.issues = issues


class InvalidAddressError(OrderError):
    """400 INVALID_ADDRESS — адрес не найден или принадлежит другому покупателю.

    Чужой/несуществующий address_id трактуем одинаково (не раскрываем существование
    чужих ресурсов), как и checkout-валидация в каноне.
    """

    def __init__(self, message: str = 'Адрес доставки не найден'):
        super().__init__('INVALID_ADDRESS', message, 400)


class InvalidPaymentMethodError(OrderError):
    """400 INVALID_PAYMENT_METHOD — платёжный метод не найден или чужой."""

    def __init__(self, message: str = 'Способ оплаты не найден'):
        super().__init__('INVALID_PAYMENT_METHOD', message, 400)


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


class DeliverNotAllowedError(OrderError):
    """409 DELIVER_NOT_ALLOWED — заказ нельзя перевести в DELIVERED.

    Канон (b2c-orders-flows.md, §"Смена статусов через Django Admin"): переход
    допустим только из DELIVERING. Любая другая исходная позиция — ошибка
    оператора (например, нельзя перескочить PAID -> DELIVERED).
    Уже DELIVERED-заказ обрабатывается use-case'ом идемпотентно (не как ошибка).
    """

    def __init__(self, current_status: str):
        super().__init__(
            'DELIVER_NOT_ALLOWED',
            f'Перевод в DELIVERED невозможен: заказ в статусе {current_status}',
            409,
            extra={'current_status': current_status},
        )
        self.current_status = current_status

from apps.errors import AppError


class CartError(AppError):
    pass


class CartItemNotFoundError(CartError):
    def __init__(self, message: str = 'Позиция корзины не найдена'):
        super().__init__('NOT_FOUND', message, 404)


class MissingCartIdentityError(CartError):
    """Ни JWT, ни X-Session-Id не предоставлены."""

    def __init__(self, message: str = 'Требуется авторизация или X-Session-Id'):
        super().__init__('MISSING_CART_IDENTITY', message, 400)


class GuestSessionRequiredError(CartError):
    """Для merge нужен X-Session-Id гостевой корзины."""

    def __init__(self, message: str = 'Для слияния корзины требуется X-Session-Id'):
        super().__init__('MISSING_SESSION_ID', message, 400)


class SkuUnavailableError(CartError):
    """SKU не найден в B2B-витрине либо товар недоступен (B2B вернул 404).

    Per OpenAPI: POST /cart/items → 404 "SKU не найден или товар недоступен".
    """

    def __init__(self, message: str = 'SKU не найден или товар недоступен'):
        super().__init__('SKU_NOT_FOUND', message, 404)


class InsufficientStockError(CartError):
    """Запрошенное количество превышает active_quantity SKU в B2B.

    Per OpenAPI: POST /cart/items и PATCH /cart/items/{sku_id} → 409 "Недостаточно остатков".
    """

    def __init__(self, message: str = 'Недостаточно остатков'):
        super().__init__('INSUFFICIENT_STOCK', message, 409)


class B2BUnavailableError(CartError):
    """B2B-витрина недоступна (сетевая ошибка / 5xx) во время валидации или обогащения.

    Per canon Flow B2C-8 edge cases #4/#5: 503, без кэша.
    """

    def __init__(self, message: str = 'Сервис каталога временно недоступен'):
        super().__init__('B2B_UNAVAILABLE', message, 503)

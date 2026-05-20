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

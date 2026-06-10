from apps.errors import AppError


class FavoriteError(AppError):
    pass


class B2BUnavailableError(FavoriteError):
    """B2B-сервис недоступен — не смогли проверить товар при добавлении."""

    def __init__(self, message: str = 'B2B сервис недоступен'):
        super().__init__('SERVICE_UNAVAILABLE', message, 503)


class ProductNotFoundError(FavoriteError):
    """Товар не найден в B2B (неизвестный/заблокированный/удалённый) — 404 на PUT."""

    def __init__(self, message: str = 'Product not found'):
        super().__init__('NOT_FOUND', message, 404)

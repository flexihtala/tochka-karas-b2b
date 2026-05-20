from apps.errors import AppError


class CatalogError(AppError):
    pass


class InvalidSortError(CatalogError):
    def __init__(
        self,
        message: str = (
            'Invalid sort parameter. Allowed: rating, popularity, price_asc, price_desc, date_desc, discount_desc'
        ),
    ):
        super().__init__('INVALID_REQUEST', message, 400)


class InvalidSearchError(CatalogError):
    """Невалидный поисковый запрос (< 3 или > 255 символов)."""

    def __init__(self, message: str):
        super().__init__('INVALID_REQUEST', message, 400)


class ProductNotFoundError(CatalogError):
    """Товар не найден / заблокирован / удалён."""

    def __init__(self, message: str = 'Product not found'):
        super().__init__('NOT_FOUND', message, 404)


class CatalogUnavailableError(CatalogError):
    """B2B недоступен — отвечаем 502 Bad Gateway."""

    def __init__(self, message: str = 'Каталог временно недоступен'):
        super().__init__('CATALOG_UNAVAILABLE', message, 502)

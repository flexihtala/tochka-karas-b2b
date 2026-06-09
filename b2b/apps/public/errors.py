from apps.errors import AppError


class PublicCatalogError(AppError):
    pass


class PublicProductNotFoundError(PublicCatalogError):
    """Товар не существует или не виден в витрине (status != MODERATED,
    deleted, либо нет SKU с active_quantity > 0). Возвращаем 404, не раскрывая
    причину (как и для seller-view — защита от IDOR-by-discovery).
    """

    def __init__(self, message: str = 'Product not found'):
        super().__init__('NOT_FOUND', message, 404)


class PublicSKUNotFoundError(PublicCatalogError):
    """SKU не существует, либо его товар не виден в витрине. 404."""

    def __init__(self, message: str = 'SKU not found'):
        super().__init__('NOT_FOUND', message, 404)

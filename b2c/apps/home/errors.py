from apps.errors import AppError


class HomeError(AppError):
    pass


class BannerNotFoundError(HomeError):
    """Клик по несуществующему баннеру → 400 BANNER_NOT_FOUND (канон B2C-14)."""

    def __init__(self, message: str = 'Баннер не найден'):
        super().__init__('BANNER_NOT_FOUND', message, 400)


class CollectionNotFoundError(HomeError):
    """Запрос товаров несуществующей подборки → 404 (канон B2C-15)."""

    def __init__(self, message: str = 'Подборка не найдена'):
        super().__init__('COLLECTION_NOT_FOUND', message, 404)

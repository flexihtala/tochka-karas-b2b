from apps.errors import AppError


class HomeError(AppError):
    pass


class BannerNotFoundError(HomeError):
    def __init__(self, message: str = 'Баннер не найден'):
        super().__init__('NOT_FOUND', message, 400)


class CollectionNotFoundError(HomeError):
    def __init__(self, message: str = 'Подборка не найдена'):
        super().__init__('NOT_FOUND', message, 404)

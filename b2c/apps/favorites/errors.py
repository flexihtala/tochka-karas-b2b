from apps.errors import AppError


class FavoriteError(AppError):
    pass


class B2BUnavailableError(FavoriteError):
    """B2B-сервис недоступен — не смогли обогатить список избранного."""

    def __init__(self, message: str = 'B2B сервис недоступен'):
        super().__init__('SERVICE_UNAVAILABLE', message, 503)

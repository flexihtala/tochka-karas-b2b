from apps.errors import AppError


class BuyerError(AppError):
    pass


class BuyerNotFoundError(BuyerError):
    def __init__(self, message: str = 'Покупатель не найден'):
        super().__init__('NOT_FOUND', message, 404)

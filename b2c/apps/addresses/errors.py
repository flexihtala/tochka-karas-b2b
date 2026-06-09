from apps.errors import AppError


class AddressError(AppError):
    pass


class AddressNotFoundError(AddressError):
    def __init__(self, message: str = 'Адрес не найден'):
        super().__init__('NOT_FOUND', message, 404)

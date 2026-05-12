from apps.errors import AppError


class ProductError(AppError):
    pass


class InvalidProductRequestError(ProductError):
    def __init__(self, message: str):
        super().__init__('INVALID_REQUEST', message, 400)

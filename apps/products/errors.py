from apps.errors import AppError


class ProductError(AppError):
    pass


class InvalidProductRequestError(ProductError):
    def __init__(self, message: str):
        super().__init__('INVALID_REQUEST', message, 400)


class ProductNotFoundError(ProductError):
    def __init__(self, message: str = 'Product not found'):
        super().__init__('NOT_FOUND', message, 404)


class ProductForbiddenError(ProductError):
    def __init__(self, code: str, message: str):
        super().__init__(code, message, 403)

from apps.errors import AppError


class SKUError(AppError):
    pass


class InvalidSKURequestError(SKUError):
    def __init__(self, message: str):
        super().__init__('INVALID_REQUEST', message, 400)


class SKUForbiddenError(SKUError):
    def __init__(self, message: str, code: str = 'FORBIDDEN'):
        super().__init__(code, message, 403)


class SKUNotFoundError(SKUError):
    def __init__(self, message: str = 'SKU not found'):
        super().__init__('NOT_FOUND', message, 404)

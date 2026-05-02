from apps.errors import AppError


class SKUError(AppError):
    pass


class InvalidSKURequestError(SKUError):
    def __init__(self, message: str):
        super().__init__('INVALID_REQUEST', message, 400)


class SKUForbiddenError(SKUError):
    def __init__(self, message: str):
        super().__init__('FORBIDDEN', message, 403)

from apps.errors import AppError


class SKUError(AppError):
    pass


class SKUInvalidRequestError(SKUError):
    def __init__(self, message: str = 'Невалидное тело запроса'):
        super().__init__('INVALID_REQUEST', message, 400)


class SKUImagesRequiredError(SKUInvalidRequestError):
    def __init__(self, message: str = 'Требуется минимум одно изображение'):
        super().__init__(message)


class SKUForbiddenError(SKUError):
    def __init__(self, message: str = 'Forbidden'):
        super().__init__('FORBIDDEN', message, 403)


class SKUHardBlockedError(SKUForbiddenError):
    def __init__(self, message: str = 'Cannot add SKU to hard-blocked product'):
        super().__init__(message)
        self.code = 'HARD_BLOCKED'


class SKUNotOwnerError(SKUForbiddenError):
    def __init__(self, message: str = 'Product does not belong to the authenticated seller'):
        super().__init__(message)
        self.code = 'NOT_OWNER'


class SKUNotFoundError(SKUError):
    def __init__(self, message: str = 'SKU not found'):
        super().__init__('NOT_FOUND', message, 404)


class ProductNotFoundError(SKUError):
    def __init__(self, message: str = 'Product not found'):
        super().__init__('NOT_FOUND', message, 404)


class SKUConflictError(SKUError):
    def __init__(self, code: str = 'CONFLICT', message: str = 'Conflict'):
        super().__init__(code, message, 409)


class SKUHasActiveReservesError(SKUConflictError):
    def __init__(self, message: str = 'Cannot delete SKU with active reserves'):
        super().__init__('HAS_ACTIVE_RESERVES', message)

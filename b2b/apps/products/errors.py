from apps.errors import AppError


class ProductError(AppError):
    pass


class ProductInvalidRequestError(ProductError):
    def __init__(self, message: str = 'Невалидное тело запроса'):
        super().__init__('INVALID_REQUEST', message, 400)


class CategoryNotFoundError(ProductError):
    def __init__(self, message: str = 'Категория не найдена'):
        super().__init__('INVALID_REQUEST', message, 400)


class ImagesRequiredError(ProductError):
    def __init__(self, message: str = 'Требуется минимум одно изображение'):
        super().__init__('INVALID_REQUEST', message, 400)


class ProductNotFoundError(ProductError):
    def __init__(self, message: str = 'Product not found'):
        super().__init__('NOT_FOUND', message, 404)


class ProductForbiddenError(ProductError):
    def __init__(self, message: str = 'Forbidden'):
        super().__init__('FORBIDDEN', message, 403)


class ProductNotOwnerError(ProductForbiddenError):
    def __init__(self, message: str = 'Product does not belong to the authenticated seller'):
        super().__init__(message)
        self.code = 'NOT_OWNER'


class ProductHardBlockedError(ProductForbiddenError):
    def __init__(self, message: str = 'Product is hard-blocked'):
        super().__init__(message)
        self.code = 'HARD_BLOCKED'


class ProductAlreadyDeletedError(ProductInvalidRequestError):
    def __init__(self, message: str = 'Product already deleted'):
        super().__init__(message)
        self.code = 'ALREADY_DELETED'

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

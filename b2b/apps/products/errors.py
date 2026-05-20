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
    """Возвращается:
    - когда товар не существует;
    - когда товар принадлежит другому продавцу (canon: НЕ 403 -- не раскрываем
      факт существования чужого товара, иначе IDOR-by-discovery).
    """

    def __init__(self, message: str = 'Product not found'):
        super().__init__('NOT_FOUND', message, 404)

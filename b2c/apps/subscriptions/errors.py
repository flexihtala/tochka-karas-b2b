from apps.errors import AppError


class SubscriptionError(AppError):
    pass


class SubscriptionAlreadyExistsError(SubscriptionError):
    def __init__(self, message: str = 'Подписка уже существует'):
        super().__init__('SUBSCRIPTION_ALREADY_EXISTS', message, 409)


class SubscriptionNotFoundError(SubscriptionError):
    def __init__(self, message: str = 'Подписка не найдена'):
        super().__init__('SUBSCRIPTION_NOT_FOUND', message, 404)


class InvalidNotifyOnError(SubscriptionError):
    def __init__(self, message: str = 'Невалидное значение notify_on'):
        super().__init__('INVALID_NOTIFY_ON', message, 400)


class ProductNotFoundError(SubscriptionError):
    def __init__(self, message: str = 'Товар не найден'):
        super().__init__('PRODUCT_NOT_FOUND', message, 404)

from apps.errors import AppError


class PaymentMethodError(AppError):
    pass


class PaymentMethodNotFoundError(PaymentMethodError):
    def __init__(self, message: str = 'Платёжный метод не найден'):
        super().__init__('NOT_FOUND', message, 404)


class InvalidCardDataError(PaymentMethodError):
    def __init__(self, message: str = 'Некорректные данные карты'):
        super().__init__('INVALID_REQUEST', message, 400)

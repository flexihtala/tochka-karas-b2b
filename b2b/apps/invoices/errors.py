from apps.errors import AppError


class InvoiceError(AppError):
    pass


class InvoiceInvalidRequestError(InvoiceError):
    def __init__(self, message: str = 'Невалидное тело запроса'):
        super().__init__('INVALID_REQUEST', message, 400)


class InvoiceEmptyItemsError(InvoiceInvalidRequestError):
    def __init__(self, message: str = 'At least one item is required'):
        super().__init__(message)


class InvoiceSKUNotFoundError(InvoiceInvalidRequestError):
    """SKU из items не существует. Канон допускает 404 — мы трактуем это как
    невалидный sku_id и возвращаем 400 INVALID_REQUEST (см. DoD-тест
    test_create_invoice_use_case::test_non_moderated_sku_returns_400 как и для
    нонмодератед — общая категория «SKU нельзя положить в накладную»).
    """

    def __init__(self, message: str = 'SKU not found'):
        super().__init__(message)


class InvoiceSKUNotModeratedError(InvoiceInvalidRequestError):
    def __init__(self, message: str = 'Invoice can only be created for MODERATED products'):
        super().__init__(message)


class InvoiceForbiddenError(InvoiceError):
    def __init__(self, message: str = 'Forbidden'):
        super().__init__('FORBIDDEN', message, 403)


class InvoiceNotOwnerError(InvoiceForbiddenError):
    def __init__(self, message: str = 'One or more SKUs do not belong to the authenticated seller'):
        super().__init__(message)
        self.code = 'NOT_OWNER'


class InvoiceNotFoundError(InvoiceError):
    def __init__(self, message: str = 'Invoice not found'):
        super().__init__('NOT_FOUND', message, 404)

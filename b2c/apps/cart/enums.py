from enum import StrEnum


class UnavailableReason(StrEnum):
    """Причина недоступности позиции корзины при обогащении из B2B.

    Возвращается в `CartItemResponseSchema.unavailable_reason`, а не сохраняется в БД —
    источник истины это B2B (см. b2c-cart-flows.md, Flow B2C-8).
    """

    BLOCKED = 'BLOCKED'
    DELETED = 'DELETED'
    OUT_OF_STOCK = 'OUT_OF_STOCK'

from enum import StrEnum


class UnavailableReason(StrEnum):
    """Причина недоступности позиции корзины при обогащении из B2B.

    Возвращается в `CartItemResponseSchema.unavailable_reason`, а не сохраняется в БД —
    источник истины это B2B (см. b2c-cart-flows.md, Flow B2C-8 §"Unavailable reasons").

    - OUT_OF_STOCK    — SKU найден, но active_quantity == 0 (или SKU нет среди skus товара).
    - PRODUCT_BLOCKED — товар заблокирован модерацией.
    - PRODUCT_DELETED — товар удалён продавцом / снят с продажи.
    - ON_MODERATION   — товар на повторной модерации (EDITED).

    Для available позиций unavailable_reason == None.
    """

    OUT_OF_STOCK = 'OUT_OF_STOCK'
    PRODUCT_BLOCKED = 'PRODUCT_BLOCKED'
    PRODUCT_DELETED = 'PRODUCT_DELETED'
    ON_MODERATION = 'ON_MODERATION'


class CartValidationIssueType(StrEnum):
    """Тип проблемы из POST /api/v1/cart/validate (см. OpenAPI CartValidationIssue)."""

    PRICE_CHANGED = 'PRICE_CHANGED'
    OUT_OF_STOCK = 'OUT_OF_STOCK'
    QUANTITY_REDUCED = 'QUANTITY_REDUCED'
    PRODUCT_BLOCKED = 'PRODUCT_BLOCKED'
    PRODUCT_DELETED = 'PRODUCT_DELETED'

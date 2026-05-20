from enum import StrEnum


class ProductStatus(StrEnum):
    """Статусы товара в B2B-кабинете."""

    CREATED = 'CREATED'
    ON_MODERATION = 'ON_MODERATION'
    MODERATED = 'MODERATED'
    BLOCKED = 'BLOCKED'
    HARD_BLOCKED = 'HARD_BLOCKED'

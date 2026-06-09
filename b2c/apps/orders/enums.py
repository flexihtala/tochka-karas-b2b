from enum import StrEnum


class OrderStatus(StrEnum):
    r"""Статусы заказа покупателя.

    Полный жизненный цикл (каноn b2c-orders-flows.md):
        CREATED -> PAID -> ASSEMBLING -> DELIVERING -> DELIVERED
                                                 \-> CANCELLED / CANCEL_PENDING

    В MVP-checkout заказ создаётся сразу в PAID (mock-оплата атомарна с checkout).
    """

    CREATED = 'CREATED'
    PAID = 'PAID'
    ASSEMBLING = 'ASSEMBLING'
    DELIVERING = 'DELIVERING'
    DELIVERED = 'DELIVERED'
    CANCELLED = 'CANCELLED'
    CANCEL_PENDING = 'CANCEL_PENDING'

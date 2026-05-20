from enum import StrEnum


class OutboxEventType(StrEnum):
    """Типы событий, которые B2C отправляет наружу через outbox.

    UNRESERVE_ORDER — ретрай unreserve при CANCEL_PENDING (US-ORD-03).
    FULFILL_ORDER — отправка fulfill после DELIVERED (US-ORD-05).
    """

    UNRESERVE_ORDER = 'UNRESERVE_ORDER'
    FULFILL_ORDER = 'FULFILL_ORDER'

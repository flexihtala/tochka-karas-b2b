from enum import StrEnum


class TicketStatus(StrEnum):
    """Статусы тикета модерации.

    Спека `neomarket-moderation.yaml`: PENDING → IN_REVIEW → (APPROVED | BLOCKED |
    HARD_BLOCKED). ARCHIVED — служебный для DELETED-событий от b2b (вне публичного
    API-флоу, спекой не определён, но необходим как маркер закрытия тикета).

    На M3 use-cases используют PENDING и ARCHIVED; HARD_BLOCKED появится в stats
    после интеграции с M2.
    """

    PENDING = 'PENDING'
    IN_REVIEW = 'IN_REVIEW'
    APPROVED = 'APPROVED'
    BLOCKED = 'BLOCKED'
    HARD_BLOCKED = 'HARD_BLOCKED'
    ARCHIVED = 'ARCHIVED'

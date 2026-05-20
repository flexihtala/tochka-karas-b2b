from enum import StrEnum


class TicketStatus(StrEnum):
    """Статусы тикета модерации.

    Жизненный цикл (упрощённый, в M3 используется только PENDING и ARCHIVED):
    - PENDING — ожидает модератора.
    - IN_REVIEW — модератор взял тикет в работу.
    - APPROVED — товар одобрен.
    - BLOCKED — товар заблокирован.
    - ARCHIVED — тикет закрыт (DELETED event от B2B).

    HARD_BLOCKED из спеки в M3 не моделируется (вводится в M2/M4); расширим позже.
    """

    PENDING = 'PENDING'
    IN_REVIEW = 'IN_REVIEW'
    APPROVED = 'APPROVED'
    BLOCKED = 'BLOCKED'
    ARCHIVED = 'ARCHIVED'

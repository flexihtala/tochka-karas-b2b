from enum import StrEnum


class TicketStatus(StrEnum):
    """Статусы тикета модерации.

    Спека: PENDING → IN_REVIEW → (APPROVED | BLOCKED). HARD_BLOCKED в M2 покрывается
    общим BLOCKED-статусом с флагом hard_block у причины — фронт/b2b различает по флагу.
    ARCHIVED — для DELETED-событий от b2b (закрытие старых тикетов).

    Решение по схеме принято осознанно: одна enum-таблица без HARD_BLOCKED отдельным
    статусом, потому что вся семантика разницы между BLOCKED и HARD_BLOCKED живёт в
    причине блокировки. См. ADR в PR-боди.
    """

    PENDING = 'PENDING'
    IN_REVIEW = 'IN_REVIEW'
    APPROVED = 'APPROVED'
    BLOCKED = 'BLOCKED'
    ARCHIVED = 'ARCHIVED'

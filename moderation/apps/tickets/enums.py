from enum import StrEnum


class TicketStatus(StrEnum):
    """Статусы тикета модерации.

    Спека: PENDING → IN_REVIEW → (APPROVED | BLOCKED | HARD_BLOCKED).
    Соответствует enum TicketStatus из neomarket-moderation.yaml.

    ARCHIVED — служебный статус для DELETED-событий от b2b (закрытие старых тикетов
    при удалении товара). В спеке не описан, потому что это внутреннее представление
    «архивного» тикета, не возвращаемое из API в нормальном флоу.
    """

    PENDING = 'PENDING'
    IN_REVIEW = 'IN_REVIEW'
    APPROVED = 'APPROVED'
    BLOCKED = 'BLOCKED'
    HARD_BLOCKED = 'HARD_BLOCKED'
    ARCHIVED = 'ARCHIVED'


class TicketKind(StrEnum):
    """Тип тикета: CREATE — на создание товара, EDIT — на редактирование.

    По спеке `neomarket-moderation.yaml` обязательное поле TicketResponse.kind.
    """

    CREATE = 'CREATE'
    EDIT = 'EDIT'

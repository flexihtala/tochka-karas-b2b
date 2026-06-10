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


class FieldReportName(StrEnum):
    """Допустимые значения field_name в замечаниях field_reports.

    Канон (moderation-flows.md#soft-block, таблица product_moderation_field_report):
    ровно 7 значений, snake_case и в БД, и в JSON API.
    """

    TITLE = 'title'
    DESCRIPTION = 'description'
    PRODUCT_IMAGES = 'product_images'
    CATEGORY = 'category'
    SKU_NAME = 'sku_name'
    SKU_IMAGE = 'sku_image'
    SKU_PRICE = 'sku_price'


class TicketKind(StrEnum):
    """Тип тикета: CREATE — на создание товара, EDIT — на редактирование.

    По спеке `neomarket-moderation.yaml` обязательное поле TicketResponse.kind.
    """

    CREATE = 'CREATE'
    EDIT = 'EDIT'

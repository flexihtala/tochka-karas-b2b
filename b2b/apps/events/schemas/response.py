from uuid import UUID

from pydantic import BaseModel

from apps.products.enums import ProductStatus


class ModerationEventResponseSchema(BaseModel):
    """Ответ на успешно обработанное moderation-событие.

    Использовуется как cached-payload в processed_events для повторных запросов
    с тем же idempotency_key. Поля минимальны — главное идемпотентно вернуть
    что-то детерминированное на повторный вызов с тем же ключом.
    """

    product_id: UUID
    status: ProductStatus

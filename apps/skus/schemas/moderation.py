from uuid import UUID

from pydantic import BaseModel


class ProductModerationEventSchema(BaseModel):
    idempotency_key: UUID
    product_id: UUID
    seller_id: UUID
    event: str
    date: str

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SubscriptionResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    product_id: UUID
    notify_on: list[str]
    created_at: datetime
    updated_at: datetime

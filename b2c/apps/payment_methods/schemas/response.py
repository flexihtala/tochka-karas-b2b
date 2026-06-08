from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PaymentMethodResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    buyer_id: UUID
    brand: str
    last4: str
    exp_year: int
    exp_month: int
    is_default: bool
    created_at: datetime
    updated_at: datetime

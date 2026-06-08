from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AddressResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    buyer_id: UUID
    country: str
    city: str
    street: str
    postal_code: str
    comment: str | None
    is_default: bool
    created_at: datetime
    updated_at: datetime

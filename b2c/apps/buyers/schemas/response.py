from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class BuyerResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    first_name: str
    last_name: str | None
    phone: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

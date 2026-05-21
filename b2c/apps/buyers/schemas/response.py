from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class BuyerResponseSchema(BaseModel):
    """BuyerResponse aligned with openapi spec.

    Spec requires {id, email, first_name, created_at}; everything else is
    nullable. `date_of_birth` is declared per spec but not stored on the
    User model yet — read-only None until migration lands.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    first_name: str
    last_name: str | None = None
    phone: str | None = None
    date_of_birth: date | None = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime | None = None

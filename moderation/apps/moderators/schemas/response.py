from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from shared.auth_lib import UserRole


class ModeratorResponseSchema(BaseModel):
    """Спека: ModeratorResponse. password_hash намеренно НЕ отдаётся в API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    first_name: str
    last_name: str | None
    role: UserRole
    is_active: bool
    created_at: datetime


class ModeratorListResponseSchema(BaseModel):
    items: list[ModeratorResponseSchema]
    total_count: int
    limit: int
    offset: int

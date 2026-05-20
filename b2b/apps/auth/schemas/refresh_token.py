from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class RefreshTokenCreateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    jti: UUID
    user_id: UUID
    issued_at: datetime
    expires_at: datetime


class RefreshTokenReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    jti: UUID
    user_id: UUID
    issued_at: datetime
    expires_at: datetime


class RefreshTokenUpdateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID | None = None
    issued_at: datetime | None = None
    expires_at: datetime | None = None

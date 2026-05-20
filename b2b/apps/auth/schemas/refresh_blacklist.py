from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class RefreshBlacklistCreateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    jti: UUID
    expires_at: datetime


class RefreshBlacklistReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    jti: UUID
    revoked_at: datetime
    expires_at: datetime


class RefreshBlacklistUpdateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    revoked_at: datetime | None = None
    expires_at: datetime | None = None

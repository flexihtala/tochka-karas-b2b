from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from shared.auth_lib import UserRole


class ModeratorCreateSchema(BaseModel):
    """DB-layer create schema (используется UserRepository.create)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID | None = None
    email: str
    password_hash: str
    role: UserRole
    is_active: bool = True
    first_name: str
    last_name: str | None = None
    password_changed_at: datetime | None = None


class ModeratorReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    password_hash: str
    role: UserRole
    is_active: bool
    first_name: str
    last_name: str | None
    password_changed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ModeratorUpdateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str | None = None
    password_hash: str | None = None
    role: UserRole | None = None
    is_active: bool | None = None
    first_name: str | None = None
    last_name: str | None = None
    password_changed_at: datetime | None = None

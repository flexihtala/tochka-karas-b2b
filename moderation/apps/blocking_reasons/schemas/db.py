from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class BlockingReasonCreateSchema(BaseModel):
    """DB-layer create schema (используется BlockingReasonRepository.create)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID | None = None
    name: str
    description: str | None = None
    hard_block: bool = False
    is_active: bool = True


class BlockingReasonReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    hard_block: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class BlockingReasonUpdateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str | None = None
    description: str | None = None
    hard_block: bool | None = None
    is_active: bool | None = None

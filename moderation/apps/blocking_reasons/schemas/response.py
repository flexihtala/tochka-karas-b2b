from uuid import UUID

from pydantic import BaseModel, ConfigDict


class BlockingReasonResponseSchema(BaseModel):
    """Спека: BlockingReasonResponse. Минимум полей по M2."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    hard_block: bool
    is_active: bool


class BlockingReasonListResponseSchema(BaseModel):
    items: list[BlockingReasonResponseSchema]

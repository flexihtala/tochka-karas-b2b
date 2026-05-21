from uuid import UUID

from pydantic import BaseModel, ConfigDict


class BlockingReasonResponseSchema(BaseModel):
    """Спека: BlockingReasonResponse — id, code, title, description, hard_block, is_active."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    title: str
    description: str | None
    hard_block: bool
    is_active: bool

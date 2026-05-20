from pydantic import BaseModel, Field


class BlockingReasonCreateRequestSchema(BaseModel):
    """POST /api/v1/blocking-reasons — admin-only."""

    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    hard_block: bool = False


class BlockingReasonUpdateRequestSchema(BaseModel):
    """PATCH /api/v1/blocking-reasons/{id} — все поля опциональны."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    hard_block: bool | None = None
    is_active: bool | None = None

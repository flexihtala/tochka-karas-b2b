from pydantic import BaseModel, Field


class BlockingReasonCreateRequestSchema(BaseModel):
    """POST /api/v1/blocking-reasons — admin-only.

    По спеке BlockingReasonCreateRequest: code (^[A-Z_]+$, maxLen 64), title (maxLen 200),
    description (опц., maxLen 2000), hard_block (обяз.).
    """

    code: str = Field(min_length=1, max_length=64, pattern=r'^[A-Z_]+$')
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    hard_block: bool


class BlockingReasonUpdateRequestSchema(BaseModel):
    """PATCH /api/v1/blocking-reasons/{id} — все поля опциональны.

    По спеке BlockingReasonUpdateRequest: title, description, is_active. Изменение code
    и hard_block по спеке не предусмотрено (терминальная семантика, code — стабильный ID).
    """

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None

"""Public (B2C-facing) request schemas."""

from uuid import UUID

from pydantic import BaseModel, Field


class BatchProductsRequestSchema(BaseModel):
    """Тело POST /public/products/batch — список product_id (макс. 100)."""

    product_ids: list[UUID] = Field(max_length=100)

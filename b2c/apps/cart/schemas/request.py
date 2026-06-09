from uuid import UUID

from pydantic import BaseModel, Field


class CartItemAddRequestSchema(BaseModel):
    sku_id: UUID
    quantity: int = Field(ge=1)


class CartItemUpdateRequestSchema(BaseModel):
    quantity: int = Field(ge=1)

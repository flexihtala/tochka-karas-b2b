from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SKUImageResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    url: str
    ordering: int


class SKUCharacteristicResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    value: str


class SKUResponseSchema(BaseModel):
    """Seller view SKU — содержит cost_price и reserved_quantity."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID
    name: str
    price: int
    cost_price: int
    discount: int
    article: str | None = None
    active_quantity: int
    reserved_quantity: int
    images: list[SKUImageResponseSchema] = Field(default_factory=list)
    characteristics: list[SKUCharacteristicResponseSchema] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

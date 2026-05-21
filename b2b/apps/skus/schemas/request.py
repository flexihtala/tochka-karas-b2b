from uuid import UUID

from pydantic import BaseModel, Field


class SKUImageCreateRequestSchema(BaseModel):
    url: str = Field(min_length=1, max_length=2048)
    ordering: int = Field(default=0, ge=0)


class SKUCharacteristicRequestSchema(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    value: str = Field(min_length=1, max_length=1024)


class SKUCreateRequestSchema(BaseModel):
    product_id: UUID
    name: str = Field(min_length=1, max_length=255)
    price: int = Field(ge=0)
    cost_price: int | None = Field(default=None, ge=0)
    discount: int = Field(default=0, ge=0)
    stock_quantity: int = Field(default=0, ge=0)
    article: str | None = Field(default=None, max_length=255)
    images: list[SKUImageCreateRequestSchema] = Field(default_factory=list)
    characteristics: list[SKUCharacteristicRequestSchema] = Field(default_factory=list)

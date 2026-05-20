from uuid import UUID

from pydantic import BaseModel, Field


class ProductImageCreateRequestSchema(BaseModel):
    url: str = Field(min_length=1, max_length=2048)
    ordering: int = Field(default=0, ge=0)


class CharacteristicRequestSchema(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    value: str = Field(min_length=1, max_length=1024)


class ProductCreateRequestSchema(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1, max_length=5000)
    category_id: UUID
    slug: str | None = Field(default=None, max_length=255)
    images: list[ProductImageCreateRequestSchema] = Field(default_factory=list)
    characteristics: list[CharacteristicRequestSchema] = Field(default_factory=list)

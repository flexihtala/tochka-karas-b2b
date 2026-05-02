from pydantic import BaseModel, Field


class ProductImageRequestSchema(BaseModel):
    url: str = Field(min_length=1, max_length=2048)
    ordering: int = Field(ge=0)


class ProductCharacteristicRequestSchema(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    value: str = Field(min_length=1, max_length=255)


class ProductCreateRequestSchema(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    category_id: str | None = None
    images: list[ProductImageRequestSchema] = Field(default_factory=list)
    characteristics: list[ProductCharacteristicRequestSchema] = Field(default_factory=list)

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


class ProductEditRequestSchema(BaseModel):
    """US-B2B-03: тело для PUT /products/{id}.

    Все поля опциональны (семантика PATCH из протокола). Если массив images/characteristics
    передан — он атомарно заменяет существующий набор. Если поле отсутствует — не меняется.
    Если передан пустой массив images=[] → 400 (хотя бы одно изображение).
    """

    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, min_length=1, max_length=5000)
    category_id: UUID | None = None
    slug: str | None = Field(default=None, max_length=255)
    images: list[ProductImageCreateRequestSchema] | None = None
    characteristics: list[CharacteristicRequestSchema] | None = None

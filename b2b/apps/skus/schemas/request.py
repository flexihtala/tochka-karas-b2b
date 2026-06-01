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
    article: str | None = Field(default=None, max_length=255)
    images: list[SKUImageCreateRequestSchema] = Field(default_factory=list)
    characteristics: list[SKUCharacteristicRequestSchema] = Field(default_factory=list)


class SKUEditRequestSchema(BaseModel):
    """US-B2B-03: тело для PUT /skus/{id}.

    Все поля опциональны (семантика PATCH из протокола). product_id НЕЛЬЗЯ менять (не в теле).
    reserved_quantity и stock_quantity редактированием не меняются. Если передан массив
    images/characteristics — он атомарно заменяет существующий набор. Если поле отсутствует
    — не меняется. Если передан пустой массив images=[] → 400.
    """

    name: str | None = Field(default=None, min_length=1, max_length=255)
    price: int | None = Field(default=None, ge=0)
    cost_price: int | None = Field(default=None, ge=0)
    discount: int | None = Field(default=None, ge=0)
    article: str | None = Field(default=None, max_length=255)
    images: list[SKUImageCreateRequestSchema] | None = None
    characteristics: list[SKUCharacteristicRequestSchema] | None = None

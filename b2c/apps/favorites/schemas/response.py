from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FavoriteResponseSchema(BaseModel):
    """Ответ POST /api/v1/favorites — без обогащения, чисто что положили."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    product_id: UUID
    created_at: datetime
    updated_at: datetime


class FavoriteProductSchema(BaseModel):
    """Элемент списка избранного — обогащённые данные товара из B2B.

    Поля payload намеренно дополнительные (extra='allow') — мы не дублируем
    точную схему B2B-продукта в b2c, чтобы избранное не падало при расширении
    B2B-схемы. Минимум — product_id (он же id товара) и favorite_id (наш PK).
    """

    model_config = ConfigDict(from_attributes=True, extra='allow')

    favorite_id: UUID
    product_id: UUID
    created_at: datetime
    product: dict[str, Any] = Field(default_factory=dict)


class FavoriteListResponseSchema(BaseModel):
    """GET /api/v1/favorites — items + total (без пагинации в текущем US)."""

    model_config = ConfigDict(from_attributes=True)

    items: list[FavoriteProductSchema] = Field(default_factory=list)
    total: int = 0

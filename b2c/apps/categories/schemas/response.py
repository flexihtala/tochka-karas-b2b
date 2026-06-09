from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CategoryResponseSchema(BaseModel):
    """Детали одной категории: GET /api/v1/categories/{id}."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    parent_id: UUID | None
    ordering: int
    created_at: datetime
    updated_at: datetime


class CategoryTreeNodeSchema(BaseModel):
    """Узел дерева категорий: GET /api/v1/categories/tree."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    parent_id: UUID | None
    ordering: int
    children: list['CategoryTreeNodeSchema'] = Field(default_factory=list)


class CategoryTreeResponseSchema(BaseModel):
    """Корневой ответ для GET /api/v1/categories/tree."""

    items: list[CategoryTreeNodeSchema]


class CategoryBreadcrumbNodeSchema(BaseModel):
    """Узел в хлебных крошках."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    level: int
    is_current: bool


class BreadcrumbsResponseSchema(BaseModel):
    """Ответ GET /api/v1/categories/breadcrumbs."""

    data: list[CategoryBreadcrumbNodeSchema]
    meta: dict[str, str]


CategoryTreeNodeSchema.model_rebuild()

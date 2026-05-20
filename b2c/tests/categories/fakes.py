from datetime import UTC, datetime
from uuid import UUID, uuid4

from apps.categories.schemas.db import CategoryCreateSchema, CategoryReadSchema, CategoryUpdateSchema


def make_category(
    *,
    name: str,
    slug: str | None = None,
    parent_id: UUID | None = None,
    ordering: int = 0,
    category_id: UUID | None = None,
) -> CategoryReadSchema:
    now = datetime.now(UTC)
    return CategoryReadSchema(
        id=category_id or uuid4(),
        name=name,
        slug=slug or name.lower().replace(' ', '-'),
        parent_id=parent_id,
        ordering=ordering,
        created_at=now,
        updated_at=now,
    )


class FakeCategoryRepository:
    """In-memory подделка CategoryRepository для тестов use-case'ов.

    Поддерживает достаточно поверхности, чтобы прогонять реальные use-case'ы
    без подключения к БД: list_all + CRUD + get_or_none.
    """

    def __init__(self) -> None:
        self.by_id: dict[UUID, CategoryReadSchema] = {}
        self.created: list[CategoryCreateSchema] = []
        self.updated: list[dict] = []
        self.deleted: list[UUID] = []

    def add(self, category: CategoryReadSchema) -> None:
        self.by_id[category.id] = category

    async def list_all(self) -> list[CategoryReadSchema]:
        return sorted(
            self.by_id.values(),
            key=lambda c: (
                c.parent_id is not None,
                str(c.parent_id) if c.parent_id else '',
                c.ordering,
                c.name,
            ),
        )

    async def get_or_none(self, category_id: UUID) -> CategoryReadSchema | None:
        return self.by_id.get(category_id)

    async def get_by_id(self, category_id: UUID) -> CategoryReadSchema | None:
        return self.by_id.get(category_id)

    async def create(self, data: CategoryCreateSchema) -> CategoryReadSchema:
        self.created.append(data)
        category_id = data.id or uuid4()
        now = datetime.now(UTC)
        category = CategoryReadSchema(
            id=category_id,
            name=data.name,
            slug=data.slug,
            parent_id=data.parent_id,
            ordering=data.ordering,
            created_at=now,
            updated_at=now,
        )
        self.by_id[category_id] = category
        return category

    async def update(self, data: CategoryUpdateSchema) -> CategoryReadSchema | None:
        existing = self.by_id.get(data.id)
        if existing is None:
            return None
        update_payload = data.model_dump(exclude_unset=True, exclude={'id'})
        self.updated.append({'id': data.id, **update_payload})
        merged = existing.model_dump()
        merged.update(update_payload)
        merged['updated_at'] = datetime.now(UTC)
        updated = CategoryReadSchema.model_validate(merged)
        self.by_id[data.id] = updated
        return updated

    async def delete(self, category_id: UUID) -> bool:
        self.deleted.append(category_id)
        return self.by_id.pop(category_id, None) is not None

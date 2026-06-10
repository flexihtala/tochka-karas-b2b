from uuid import UUID

from sqlalchemy import select

from apps.categories.models import Category
from apps.categories.schemas.db import CategoryCreateSchema, CategoryReadSchema, CategoryUpdateSchema
from shared.db import DBCrudRepository


class CategoryRepository(DBCrudRepository[Category, CategoryCreateSchema, CategoryReadSchema, CategoryUpdateSchema]):
    """Репозиторий категорий B2C (adjacency-list).

    Хранит локальное зеркало дерева категорий. Используется публичными
    эндпоинтами /api/v1/categories/*.
    """

    async def list_all(self) -> list[CategoryReadSchema]:
        """Плоский список всех категорий, отсортированный по parent_id, ordering, name."""
        query = select(Category).order_by(
            Category.parent_id.asc().nulls_first(),
            Category.ordering.asc(),
            Category.name.asc(),
        )

        async with self.session_manager.get_session() as session:
            models = (await session.execute(query)).scalars().all()

        return [self.model_validate(model) for model in models]

    async def get_by_id(self, category_id: UUID) -> CategoryReadSchema | None:
        return await self.get_or_none(category_id)

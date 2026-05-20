from uuid import UUID

from apps.categories.models import Category
from apps.categories.schemas import CategoryCreateSchema, CategoryReadSchema, CategoryUpdateSchema
from db import DBCrudRepository


class CategoryRepository(DBCrudRepository[Category, CategoryCreateSchema, CategoryReadSchema, CategoryUpdateSchema]):
    async def exists(self, category_id: UUID) -> bool:
        return await self.get_or_none(category_id) is not None

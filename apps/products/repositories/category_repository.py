from apps.products.models import Category
from apps.products.schemas.category import CategoryCreateSchema, CategoryReadSchema, CategoryUpdateSchema
from db import DBCrudRepository


class CategoryRepository(DBCrudRepository[Category, CategoryCreateSchema, CategoryReadSchema, CategoryUpdateSchema]):
    pass

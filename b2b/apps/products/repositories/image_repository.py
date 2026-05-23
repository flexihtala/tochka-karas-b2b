from uuid import UUID

from sqlalchemy import delete, select

from apps.products.models import ProductImage
from apps.products.schemas.db import (
    ProductImageCreateSchema,
    ProductImageReadSchema,
    ProductImageUpdateSchema,
)
from db import DBCrudRepository


class ProductImageRepository(
    DBCrudRepository[ProductImage, ProductImageCreateSchema, ProductImageReadSchema, ProductImageUpdateSchema]
):
    async def list_by_product(self, product_id: UUID) -> list[ProductImageReadSchema]:
        query = select(ProductImage).where(ProductImage.product_id == product_id).order_by(ProductImage.ordering)
        async with self.session_manager.get_session() as session:
            result = (await session.execute(query)).scalars().all()
        return [self.model_validate(m) for m in result]

    async def delete_by_product(self, product_id: UUID) -> int:
        """Удаляет все изображения товара. Используется в edit-use-case для атомарной замены."""
        query = delete(ProductImage).where(ProductImage.product_id == product_id)
        async with self.session_manager.get_session() as session:
            result = await session.execute(query)
        return int(result.rowcount or 0)

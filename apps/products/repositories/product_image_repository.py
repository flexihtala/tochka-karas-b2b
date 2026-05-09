from uuid import UUID

from sqlalchemy import delete

from apps.products.models import ProductImage
from apps.products.schemas.product import ProductImageCreateSchema, ProductImageReadSchema, ProductImageUpdateSchema
from db import DBCrudRepository


class ProductImageRepository(
    DBCrudRepository[ProductImage, ProductImageCreateSchema, ProductImageReadSchema, ProductImageUpdateSchema]
):
    async def delete_by_product_id(self, product_id: UUID) -> None:
        query = delete(ProductImage).where(ProductImage.product_id == product_id)
        async with self.session_manager.get_session() as session:
            await session.execute(query)

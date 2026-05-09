from uuid import UUID

from sqlalchemy import delete

from apps.skus.models import SKUImage
from apps.skus.schemas import SKUImageCreateSchema, SKUImageReadSchema, SKUImageUpdateSchema
from db import DBCrudRepository


class SKUImageRepository(DBCrudRepository[SKUImage, SKUImageCreateSchema, SKUImageReadSchema, SKUImageUpdateSchema]):
    async def delete_by_sku_id(self, sku_id: UUID) -> None:
        query = delete(SKUImage).where(SKUImage.sku_id == sku_id)
        async with self.session_manager.get_session() as session:
            await session.execute(query)

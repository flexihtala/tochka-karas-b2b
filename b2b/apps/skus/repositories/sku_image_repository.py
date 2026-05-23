from uuid import UUID

from sqlalchemy import delete, select

from apps.skus.models import SKUImage
from apps.skus.schemas.db import (
    SKUImageCreateSchema,
    SKUImageReadSchema,
    SKUImageUpdateSchema,
)
from db import DBCrudRepository


class SKUImageRepository(DBCrudRepository[SKUImage, SKUImageCreateSchema, SKUImageReadSchema, SKUImageUpdateSchema]):
    async def list_by_sku(self, sku_id: UUID) -> list[SKUImageReadSchema]:
        query = select(SKUImage).where(SKUImage.sku_id == sku_id).order_by(SKUImage.ordering)
        async with self.session_manager.get_session() as session:
            result = (await session.execute(query)).scalars().all()
        return [self.model_validate(m) for m in result]

    async def delete_by_sku(self, sku_id: UUID) -> int:
        """Удаляет все изображения SKU. Используется в edit-use-case для атомарной замены."""
        query = delete(SKUImage).where(SKUImage.sku_id == sku_id)
        async with self.session_manager.get_session() as session:
            result = await session.execute(query)
        return int(result.rowcount or 0)

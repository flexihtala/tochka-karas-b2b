from uuid import UUID

from sqlalchemy import func, select

from apps.skus.models import SKU
from apps.skus.schemas.db import SKUCreateSchema, SKUReadSchema, SKUUpdateSchema
from db import DBCrudRepository


class SKURepository(DBCrudRepository[SKU, SKUCreateSchema, SKUReadSchema, SKUUpdateSchema]):
    async def count_by_product(self, product_id: UUID) -> int:
        query = select(func.count()).select_from(SKU).where(SKU.product_id == product_id)
        async with self.session_manager.get_session() as session:
            return int((await session.execute(query)).scalar_one())

    async def list_ids_by_product(self, product_id: UUID) -> list[UUID]:
        """Возвращает список UUID всех SKU у товара. Используется для cascade-события PRODUCT_DELETED в B2C."""
        query = select(SKU.id).where(SKU.product_id == product_id)
        async with self.session_manager.get_session() as session:
            return list((await session.execute(query)).scalars().all())

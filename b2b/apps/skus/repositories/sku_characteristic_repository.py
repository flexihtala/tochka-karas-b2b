from uuid import UUID

from sqlalchemy import delete, select

from apps.skus.models import SKUCharacteristicValue
from apps.skus.schemas.db import (
    SKUCharacteristicValueCreateSchema,
    SKUCharacteristicValueReadSchema,
    SKUCharacteristicValueUpdateSchema,
)
from db import DBCrudRepository


class SKUCharacteristicValueRepository(
    DBCrudRepository[
        SKUCharacteristicValue,
        SKUCharacteristicValueCreateSchema,
        SKUCharacteristicValueReadSchema,
        SKUCharacteristicValueUpdateSchema,
    ]
):
    async def list_by_sku(self, sku_id: UUID) -> list[SKUCharacteristicValueReadSchema]:
        query = select(SKUCharacteristicValue).where(SKUCharacteristicValue.sku_id == sku_id)
        async with self.session_manager.get_session() as session:
            result = (await session.execute(query)).scalars().all()
        return [self.model_validate(m) for m in result]

    async def delete_by_sku(self, sku_id: UUID) -> int:
        """Удаляет все характеристики SKU. Используется в edit-use-case для атомарной замены."""
        query = delete(SKUCharacteristicValue).where(SKUCharacteristicValue.sku_id == sku_id)
        async with self.session_manager.get_session() as session:
            result = await session.execute(query)
        return int(result.rowcount or 0)

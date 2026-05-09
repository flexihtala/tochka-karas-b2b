from uuid import UUID

from sqlalchemy import delete

from apps.skus.models import SKUCharacteristic
from apps.skus.schemas import (
    SKUCharacteristicCreateSchema,
    SKUCharacteristicReadSchema,
    SKUCharacteristicUpdateSchema,
)
from db import DBCrudRepository


class SKUCharacteristicRepository(
    DBCrudRepository[
        SKUCharacteristic,
        SKUCharacteristicCreateSchema,
        SKUCharacteristicReadSchema,
        SKUCharacteristicUpdateSchema,
    ]
):
    async def delete_by_sku_id(self, sku_id: UUID) -> None:
        query = delete(SKUCharacteristic).where(SKUCharacteristic.sku_id == sku_id)
        async with self.session_manager.get_session() as session:
            await session.execute(query)

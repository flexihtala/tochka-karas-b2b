from uuid import UUID

from sqlalchemy import select

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

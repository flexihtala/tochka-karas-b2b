from uuid import UUID

from sqlalchemy import delete, select

from apps.products.models import CharacteristicValue
from apps.products.schemas.db import (
    CharacteristicValueCreateSchema,
    CharacteristicValueReadSchema,
    CharacteristicValueUpdateSchema,
)
from db import DBCrudRepository


class CharacteristicValueRepository(
    DBCrudRepository[
        CharacteristicValue,
        CharacteristicValueCreateSchema,
        CharacteristicValueReadSchema,
        CharacteristicValueUpdateSchema,
    ]
):
    async def list_by_product(self, product_id: UUID) -> list[CharacteristicValueReadSchema]:
        query = select(CharacteristicValue).where(CharacteristicValue.product_id == product_id)
        async with self.session_manager.get_session() as session:
            result = (await session.execute(query)).scalars().all()
        return [self.model_validate(m) for m in result]

    async def delete_by_product(self, product_id: UUID) -> int:
        """Удаляет все характеристики товара. Используется в edit-use-case для атомарной замены."""
        query = delete(CharacteristicValue).where(CharacteristicValue.product_id == product_id)
        async with self.session_manager.get_session() as session:
            result = await session.execute(query)
        return int(result.rowcount or 0)

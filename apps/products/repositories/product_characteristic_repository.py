from uuid import UUID

from sqlalchemy import delete

from apps.products.models import ProductCharacteristic
from apps.products.schemas.product import (
    ProductCharacteristicCreateSchema,
    ProductCharacteristicReadSchema,
    ProductCharacteristicUpdateSchema,
)
from db import DBCrudRepository


class ProductCharacteristicRepository(
    DBCrudRepository[
        ProductCharacteristic,
        ProductCharacteristicCreateSchema,
        ProductCharacteristicReadSchema,
        ProductCharacteristicUpdateSchema,
    ]
):
    async def delete_by_product_id(self, product_id: UUID) -> None:
        query = delete(ProductCharacteristic).where(ProductCharacteristic.product_id == product_id)
        async with self.session_manager.get_session() as session:
            await session.execute(query)

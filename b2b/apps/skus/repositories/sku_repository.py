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
            rows = (await session.execute(query)).scalars().all()
            return list(rows)

    async def list_full_by_product(self, product_id: UUID) -> list[SKUReadSchema]:
        """Возвращает полные SKU-модели товара (seller-view), отсортированные по дате создания.

        Используется в карточке товара продавца (US-B2B-05), чтобы вернуть все
        варианты с cost_price / reserved_quantity. Картинки и характеристики SKU
        подгружаются вызывающей стороной (отдельные репозитории).
        """
        query = select(SKU).where(SKU.product_id == product_id).order_by(SKU.created_at, SKU.id)
        async with self.session_manager.get_session() as session:
            rows = (await session.execute(query)).scalars().all()
        return [self.model_validate(m) for m in rows]

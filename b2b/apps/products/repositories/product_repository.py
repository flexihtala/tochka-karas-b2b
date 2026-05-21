from uuid import UUID

from sqlalchemy import select

from apps.products.models import Product
from apps.products.schemas.db import ProductCreateSchema, ProductReadSchema, ProductUpdateSchema
from db import DBCrudRepository


class ProductRepository(DBCrudRepository[Product, ProductCreateSchema, ProductReadSchema, ProductUpdateSchema]):
    async def list_by_seller(self, seller_id: UUID, *, include_deleted: bool = False) -> list[ProductReadSchema]:
        """Список товаров продавца. По умолчанию soft-deleted скрыты (US-B2B-4).

        Используется для seller list endpoint (когда появится) и в тестах
        для проверки, что мягко удалённый товар не виден.
        """
        query = select(Product).where(Product.seller_id == seller_id)
        if not include_deleted:
            query = query.where(Product.deleted.is_(False))

        async with self.session_manager.get_session() as session:
            rows = (await session.execute(query)).scalars().all()
            return [self.model_validate(row) for row in rows]

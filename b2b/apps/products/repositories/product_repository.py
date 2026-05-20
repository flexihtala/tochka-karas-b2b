from uuid import UUID

from sqlalchemy import func, select

from apps.products.enums import ProductStatus
from apps.products.models import Product
from apps.products.schemas.db import ProductCreateSchema, ProductReadSchema, ProductUpdateSchema
from db import DBCrudRepository


class ProductRepository(DBCrudRepository[Product, ProductCreateSchema, ProductReadSchema, ProductUpdateSchema]):
    async def list_for_seller(
        self,
        *,
        seller_id: UUID,
        limit: int,
        offset: int,
        status: ProductStatus | None = None,
        include_deleted: bool = False,
        search: str | None = None,
    ) -> tuple[list[ProductReadSchema], int]:
        """Список товаров продавца с фильтрами + total_count.

        Фильтр `seller_id` берётся из JWT-клеймов в use case → сюда передаётся уже доверенный id.
        Поиск по title через ILIKE (case-insensitive).
        Возвращает кортеж (items, total_count) — total считается до пагинации.
        """
        conditions = [Product.seller_id == seller_id]
        if not include_deleted:
            conditions.append(Product.deleted.is_(False))
        if status is not None:
            conditions.append(Product.status == status)
        if search:
            conditions.append(Product.title.ilike(f'%{search}%'))

        count_query = select(func.count()).select_from(Product).where(*conditions)
        items_query = select(Product).where(*conditions).order_by(Product.created_at.desc()).offset(offset).limit(limit)

        async with self.session_manager.get_session() as session:
            total_count = (await session.execute(count_query)).scalar_one()
            models = (await session.execute(items_query)).scalars().all()

        return [self.model_validate(m) for m in models], int(total_count)

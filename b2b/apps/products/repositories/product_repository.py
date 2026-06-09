from typing import NamedTuple
from uuid import UUID

from sqlalchemy import func, select

from apps.products.enums import ProductStatus
from apps.products.models import Product
from apps.products.schemas.db import ProductCreateSchema, ProductReadSchema, ProductUpdateSchema
from apps.skus.models import SKU
from db import DBCrudRepository


class SellerProductRow(NamedTuple):
    """Строка списка товаров продавца: сам товар + агрегаты по его SKU.

    skus_count — число SKU товара; total_active_quantity — суммарный
    active_quantity по всем SKU товара.
    """

    product: ProductReadSchema
    skus_count: int
    total_active_quantity: int


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
    ) -> tuple[list[SellerProductRow], int]:
        """Список товаров продавца с фильтрами, агрегатами по SKU и total_count.

        Фильтр `seller_id` берётся из JWT-клеймов в use case → сюда передаётся уже доверенный id.
        Поиск по title через ILIKE (case-insensitive).

        Агрегаты `skus_count` и `total_active_quantity` считаются коррелированными
        скалярными подзапросами в том же SELECT, что возвращает страницу товаров —
        один round-trip на страницу, без N+1 (см. ADR US-B2B-11). total_count
        считается отдельным COUNT до пагинации.
        """
        conditions = [Product.seller_id == seller_id]
        if not include_deleted:
            conditions.append(Product.deleted.is_(False))
        if status is not None:
            conditions.append(Product.status == status)
        if search:
            conditions.append(Product.title.ilike(f'%{search}%'))

        skus_count_subq = (
            select(func.count(SKU.id)).where(SKU.product_id == Product.id).correlate(Product).scalar_subquery()
        )
        total_active_subq = (
            select(func.coalesce(func.sum(SKU.active_quantity), 0))
            .where(SKU.product_id == Product.id)
            .correlate(Product)
            .scalar_subquery()
        )

        count_query = select(func.count()).select_from(Product).where(*conditions)
        items_query = (
            select(
                Product,
                skus_count_subq.label('skus_count'),
                total_active_subq.label('total_active_quantity'),
            )
            .where(*conditions)
            .order_by(Product.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

        async with self.session_manager.get_session() as session:
            total_count = (await session.execute(count_query)).scalar_one()
            result = (await session.execute(items_query)).all()

        rows = [
            SellerProductRow(
                product=self.model_validate(row[0]),
                skus_count=int(row.skus_count),
                total_active_quantity=int(row.total_active_quantity),
            )
            for row in result
        ]
        return rows, int(total_count)

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

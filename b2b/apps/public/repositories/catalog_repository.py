"""Репозиторий витрины для B2C.

Видимость товара (см. canon B2B-7):
    Product.status == MODERATED  AND
    Product.deleted == False     AND
    EXISTS (SELECT 1 FROM skus WHERE product_id = product.id AND active_quantity > 0)
"""

from uuid import UUID

from sqlalchemy import exists, func, select
from sqlalchemy.orm import selectinload

from apps.products.enums import ProductStatus
from apps.products.models import Product
from apps.skus.models import SKU
from db import SessionManager


class PublicCatalogRepository:
    """Репозиторий витрины. Имплементирует PublicCatalogRepositoryProtocol."""

    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager

    async def list_visible(
        self,
        *,
        ids: list[UUID] | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Product], int]:
        """Список видимых товаров + total_count.

        Видимый = MODERATED + not deleted + хотя бы один SKU.active_quantity > 0.

        Если ids — не None, добавляется фильтр Product.id IN (ids).
        """
        visibility_predicate = (
            (Product.status == ProductStatus.MODERATED)
            & (Product.deleted.is_(False))
            & exists().where((SKU.product_id == Product.id) & (SKU.active_quantity > 0))
        )

        base_query = select(Product).where(visibility_predicate)
        count_query = select(func.count()).select_from(Product).where(visibility_predicate)

        if ids is not None:
            base_query = base_query.where(Product.id.in_(ids))
            count_query = count_query.where(Product.id.in_(ids))

        # Eager-load связанные коллекции, чтобы не было N+1.
        list_query = (
            base_query.options(
                selectinload(Product.images),
                selectinload(Product.characteristics),
            )
            .order_by(Product.created_at.desc(), Product.id.desc())
            .limit(limit)
            .offset(offset)
        )

        async with self.session_manager.get_session() as session:
            products = (await session.execute(list_query)).scalars().all()
            total = int((await session.execute(count_query)).scalar_one())

            # Подгружаем SKU + их вложенные коллекции отдельным запросом
            # (на Product у нас нет relationship-а к SKU; см. apps/products/models/product.py).
            product_ids = [product.id for product in products]
            skus_by_product: dict[UUID, list[SKU]] = {pid: [] for pid in product_ids}

            if product_ids:
                sku_query = (
                    select(SKU)
                    .where(SKU.product_id.in_(product_ids))
                    .options(
                        selectinload(SKU.images),
                        selectinload(SKU.characteristics),
                    )
                    .order_by(SKU.created_at.asc(), SKU.id.asc())
                )
                skus = (await session.execute(sku_query)).scalars().all()
                for sku in skus:
                    skus_by_product[sku.product_id].append(sku)

            # Прикрепляем skus к продукту как обычный list-атрибут — UseCase ожидает .skus.
            for product in products:
                product.skus = skus_by_product.get(product.id, [])  # type: ignore[attr-defined]

            return list(products), total

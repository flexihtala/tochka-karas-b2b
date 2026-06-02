"""Репозиторий витрины для B2C.

Видимость товара (см. canon B2B-7 + OpenAPI Public Catalog):
    Product.status == MODERATED  AND
    Product.deleted == False     AND
    EXISTS (SELECT 1 FROM skus WHERE product_id = product.id AND active_quantity > 0)

HARD_BLOCKED товары отсекаются условием status == MODERATED.

Производные поля для коротких карточек:
    min_price   — min(sku.price) среди SKU c active_quantity > 0;
    cover_image — url первого изображения товара (по ordering) или None.

Семантика characteristic-фильтров (?filters[key]=value):
    товар проходит фильтр, если для КАЖДОГО ключа существует характеристика
    товара (CharacteristicValue) с name == key и value IN переданные значения.
    AND между разными ключами, OR между значениями одного ключа.

Сортировка (?sort):
    price_asc / price_desc — по min(sku.price) видимых SKU (NULLS LAST);
    created_desc           — по Product.created_at desc (значение по умолчанию);
    popular                — MVP: эвристики нет, деградирует до created_desc.
"""

from uuid import UUID

from sqlalchemy import Select, exists, func, or_, select
from sqlalchemy.orm import aliased, selectinload

from apps.products.enums import ProductStatus
from apps.products.models import CharacteristicValue, Product, ProductImage
from apps.public.enums import CatalogSort
from apps.skus.models import SKU
from db import SessionManager


def _visibility_predicate():
    """Условие видимости товара в витрине (status + not deleted + есть остаток)."""
    return (
        (Product.status == ProductStatus.MODERATED)
        & (Product.deleted.is_(False))
        & exists().where((SKU.product_id == Product.id) & (SKU.active_quantity > 0))
    )


def _min_price_subquery():
    """Скалярный коррелированный подзапрос: минимальная цена среди SKU с остатком."""
    return (
        select(func.min(SKU.price)).where((SKU.product_id == Product.id) & (SKU.active_quantity > 0)).scalar_subquery()
    )


def _cover_image_subquery():
    """Скалярный коррелированный подзапрос: url первого изображения товара (по ordering)."""
    return (
        select(ProductImage.url)
        .where(ProductImage.product_id == Product.id)
        .order_by(ProductImage.ordering.asc(), ProductImage.id.asc())
        .limit(1)
        .scalar_subquery()
    )


class PublicCatalogRepository:
    """Репозиторий витрины. Имплементирует PublicCatalogRepositoryProtocol."""

    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager

    @staticmethod
    async def _attach_skus(session, products: list[Product]) -> None:
        """Подгружает SKU (с images/characteristics) к товарам и кладёт в product.skus.

        У Product нет relationship к SKU (см. apps/products/models/product.py),
        поэтому грузим отдельным запросом, чтобы не было N+1.
        """
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
        for product in products:
            product.skus = skus_by_product.get(product.id, [])  # type: ignore[attr-defined]

    @staticmethod
    def _apply_filters(
        query: Select,
        *,
        category_id: UUID | None,
        search: str | None,
        min_price: int | None,
        max_price: int | None,
        seller_id: UUID | None,
        filters: dict[str, list[str]] | None,
    ) -> Select:
        if category_id is not None:
            query = query.where(Product.category_id == category_id)
        if seller_id is not None:
            query = query.where(Product.seller_id == seller_id)
        if search:
            pattern = f'%{search}%'
            query = query.where(or_(Product.title.ilike(pattern), Product.description.ilike(pattern)))

        # min_price / max_price применяются к минимальной цене видимых SKU товара.
        if min_price is not None:
            query = query.where(
                exists().where((SKU.product_id == Product.id) & (SKU.active_quantity > 0) & (SKU.price >= min_price))
            )
        if max_price is not None:
            query = query.where(
                exists().where((SKU.product_id == Product.id) & (SKU.active_quantity > 0) & (SKU.price <= max_price))
            )

        # Characteristic-фильтры: AND между ключами, OR между значениями ключа.
        if filters:
            for name, values in filters.items():
                if not values:
                    continue
                query = query.where(
                    exists().where(
                        (CharacteristicValue.product_id == Product.id)
                        & (CharacteristicValue.name == name)
                        & (CharacteristicValue.value.in_(values))
                    )
                )
        return query

    @staticmethod
    def _apply_sort(query: Select, sort: CatalogSort, min_price_expr) -> Select:
        if sort == CatalogSort.PRICE_ASC:
            return query.order_by(min_price_expr.asc().nullslast(), Product.id.asc())
        if sort == CatalogSort.PRICE_DESC:
            return query.order_by(min_price_expr.desc().nullslast(), Product.id.asc())
        # created_desc и popular (MVP fallback) — по дате создания, новые первыми.
        return query.order_by(Product.created_at.desc(), Product.id.desc())

    async def list_short(
        self,
        *,
        category_id: UUID | None = None,
        search: str | None = None,
        min_price: int | None = None,
        max_price: int | None = None,
        seller_id: UUID | None = None,
        filters: dict[str, list[str]] | None = None,
        sort: CatalogSort = CatalogSort.CREATED_DESC,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Product], int]:
        """Короткие карточки видимых товаров + total_count (с фильтрами и сортировкой)."""
        visibility = _visibility_predicate()
        min_price_expr = _min_price_subquery()
        cover_expr = _cover_image_subquery()

        base = select(Product).where(visibility)
        base = self._apply_filters(
            base,
            category_id=category_id,
            search=search,
            min_price=min_price,
            max_price=max_price,
            seller_id=seller_id,
            filters=filters,
        )

        count_query = select(func.count()).select_from(base.order_by(None).subquery())

        list_query = select(
            Product,
            min_price_expr.label('min_price'),
            cover_expr.label('cover_image'),
        ).where(visibility)
        list_query = self._apply_filters(
            list_query,
            category_id=category_id,
            search=search,
            min_price=min_price,
            max_price=max_price,
            seller_id=seller_id,
            filters=filters,
        )
        list_query = self._apply_sort(list_query, sort, min_price_expr).limit(limit).offset(offset)

        async with self.session_manager.get_session() as session:
            rows = (await session.execute(list_query)).all()
            total = int((await session.execute(count_query)).scalar_one())

        products: list[Product] = []
        for product, min_p, cover in rows:
            product.min_price = int(min_p) if min_p is not None else 0  # type: ignore[attr-defined]
            product.cover_image = cover  # type: ignore[attr-defined]
            products.append(product)
        return products, total

    async def get_full_by_id(self, product_id: UUID) -> Product | None:
        """Полная карточка видимого товара или None."""
        query = (
            select(Product)
            .where(_visibility_predicate() & (Product.id == product_id))
            .options(
                selectinload(Product.images),
                selectinload(Product.characteristics),
            )
        )
        async with self.session_manager.get_session() as session:
            product = (await session.execute(query)).scalar_one_or_none()
            if product is None:
                return None
            await self._attach_skus(session, [product])
            return product

    async def list_full_by_ids(self, product_ids: list[UUID]) -> list[Product]:
        """Видимое подмножество товаров по списку id (полные карточки)."""
        if not product_ids:
            return []
        query = (
            select(Product)
            .where(_visibility_predicate() & (Product.id.in_(product_ids)))
            .options(
                selectinload(Product.images),
                selectinload(Product.characteristics),
            )
            .order_by(Product.created_at.desc(), Product.id.desc())
        )
        async with self.session_manager.get_session() as session:
            products = list((await session.execute(query)).scalars().all())
            await self._attach_skus(session, products)
            return products

    async def list_similar_short(self, product_id: UUID, *, limit: int = 10) -> list[Product]:
        """Случайная выборка видимых товаров той же категории (исключая сам товар).

        Категория берётся из исходного товара (он не обязан быть видимым сам по
        себе). Если товар не найден — пустой список.
        """
        min_price_expr = _min_price_subquery()
        cover_expr = _cover_image_subquery()

        async with self.session_manager.get_session() as session:
            category_id = (
                await session.execute(select(Product.category_id).where(Product.id == product_id))
            ).scalar_one_or_none()
            if category_id is None:
                return []

            query = (
                select(
                    Product,
                    min_price_expr.label('min_price'),
                    cover_expr.label('cover_image'),
                )
                .where(_visibility_predicate() & (Product.category_id == category_id) & (Product.id != product_id))
                .order_by(func.random())
                .limit(limit)
            )
            rows = (await session.execute(query)).all()

        products: list[Product] = []
        for product, min_p, cover in rows:
            product.min_price = int(min_p) if min_p is not None else 0  # type: ignore[attr-defined]
            product.cover_image = cover  # type: ignore[attr-defined]
            products.append(product)
        return products

    async def get_public_sku(self, sku_id: UUID) -> SKU | None:
        """SKU витрины (его товар должен быть видимым), иначе None."""
        # Алиас, чтобы проверка "есть SKU с остатком" не ссылалась на внешний SKU.
        stock_sku = aliased(SKU)
        product_visible = (
            select(Product.id)
            .where(
                (Product.id == SKU.product_id)
                & (Product.status == ProductStatus.MODERATED)
                & (Product.deleted.is_(False))
                & exists().where((stock_sku.product_id == Product.id) & (stock_sku.active_quantity > 0))
            )
            .exists()
        )
        query = (
            select(SKU)
            .where((SKU.id == sku_id) & product_visible)
            .options(
                selectinload(SKU.images),
                selectinload(SKU.characteristics),
            )
        )
        async with self.session_manager.get_session() as session:
            return (await session.execute(query)).scalar_one_or_none()

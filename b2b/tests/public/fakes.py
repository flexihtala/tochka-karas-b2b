"""Фейки для tests/public.

Имитируют поведение PublicCatalogRepository, но без БД. Применяют те же
условия видимости (status == MODERATED, deleted == False, есть SKU с
active_quantity > 0) + фильтры/сортировку — это позволяет тестировать use-case'ы
как против реального репозитория, так и поверх фейков.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from apps.products.enums import ProductStatus
from apps.public.enums import CatalogSort


@dataclass
class FakeImage:
    id: UUID
    url: str
    ordering: int


@dataclass
class FakeCharacteristic:
    id: UUID
    name: str
    value: str


@dataclass
class FakeSKU:
    id: UUID
    product_id: UUID
    name: str
    price: int
    discount: int
    active_quantity: int
    article: str | None = None
    images: list[FakeImage] = field(default_factory=list)
    characteristics: list[FakeCharacteristic] = field(default_factory=list)
    # Эти поля присутствуют у реальной модели SKU, но в public-response их нет —
    # фейк держит их, чтобы тест мог assert-ить отсутствие в JSON.
    cost_price: int = 0
    reserved_quantity: int = 0

    @property
    def stock_quantity(self) -> int:
        """Как у реальной модели SKU: active + reserved."""
        return self.active_quantity + self.reserved_quantity


@dataclass
class FakeProduct:
    id: UUID
    seller_id: UUID
    category_id: UUID
    title: str
    slug: str
    description: str
    status: ProductStatus
    deleted: bool
    created_at: datetime
    updated_at: datetime
    images: list[FakeImage] = field(default_factory=list)
    characteristics: list[FakeCharacteristic] = field(default_factory=list)
    skus: list[FakeSKU] = field(default_factory=list)
    # Производные поля коротких карточек проставляет репозиторий при выборке.
    min_price: int = 0
    cover_image: str | None = None


def _make_sku(
    *,
    product_id: UUID,
    active_quantity: int,
    name: str = '256GB Black',
    price: int = 12_999_000,
    cost_price: int = 9_500_000,
    reserved_quantity: int = 0,
    discount: int = 0,
    article: str | None = None,
    characteristics: list[FakeCharacteristic] | None = None,
) -> FakeSKU:
    return FakeSKU(
        id=uuid4(),
        product_id=product_id,
        name=name,
        price=price,
        discount=discount,
        active_quantity=active_quantity,
        article=article,
        cost_price=cost_price,
        reserved_quantity=reserved_quantity,
        characteristics=characteristics or [],
    )


def _make_product(
    *,
    status: ProductStatus = ProductStatus.MODERATED,
    deleted: bool = False,
    seller_id: UUID | None = None,
    category_id: UUID | None = None,
    title: str = 'iPhone 15 Pro Max',
    slug: str = 'iphone-15-pro-max',
    description: str = 'Флагман Apple',
    skus: list[FakeSKU] | None = None,
    images: list[FakeImage] | None = None,
    characteristics: list[FakeCharacteristic] | None = None,
    created_at: datetime | None = None,
) -> FakeProduct:
    now = created_at or datetime.now(UTC)
    return FakeProduct(
        id=uuid4(),
        seller_id=seller_id or uuid4(),
        category_id=category_id or uuid4(),
        title=title,
        slug=slug,
        description=description,
        status=status,
        deleted=deleted,
        created_at=now,
        updated_at=now,
        images=images or [],
        characteristics=characteristics or [],
        skus=skus or [],
    )


def _visible_min_price(product: FakeProduct) -> int:
    prices = [sku.price for sku in product.skus if sku.active_quantity > 0]
    return min(prices) if prices else 0


def _cover_image(product: FakeProduct) -> str | None:
    if not product.images:
        return None
    return sorted(product.images, key=lambda i: (i.ordering, str(i.id)))[0].url


class FakePublicCatalogRepository:
    """Фейк репозитория витрины.

    Внутри держит список FakeProduct (со связанными SKU). Реализует те же 5
    методов, что и реальный PublicCatalogRepository, с теми же условиями
    видимости/фильтрации/сортировки.
    """

    def __init__(self) -> None:
        self.products: list[FakeProduct] = []
        # Учёт случайной сортировки для теста similar (random → детерминируем seed в тесте).

    def add_product(
        self,
        *,
        status: ProductStatus = ProductStatus.MODERATED,
        deleted: bool = False,
        skus: list[FakeSKU] | None = None,
        with_sku_active_quantity: int | None = 10,
        seller_id: UUID | None = None,
        category_id: UUID | None = None,
        title: str = 'iPhone 15 Pro Max',
        description: str = 'Флагман Apple',
        images: list[FakeImage] | None = None,
        characteristics: list[FakeCharacteristic] | None = None,
        created_at: datetime | None = None,
    ) -> FakeProduct:
        """Хелпер для тестов. По умолчанию создаёт видимый товар: MODERATED,
        not deleted, c одним SKU active_quantity > 0.

        Если передан `with_sku_active_quantity=None`, SKU не создаётся (товар без SKU).
        Можно передать собственный `skus` — тогда with_sku_active_quantity игнорируется.
        """
        product = _make_product(
            status=status,
            deleted=deleted,
            seller_id=seller_id,
            category_id=category_id,
            title=title,
            description=description,
            images=images,
            characteristics=characteristics,
            created_at=created_at,
        )
        if skus is not None:
            for sku in skus:
                sku.product_id = product.id
            product.skus = skus
        elif with_sku_active_quantity is not None:
            product.skus = [_make_sku(product_id=product.id, active_quantity=with_sku_active_quantity)]
        self.products.append(product)
        return product

    def _is_visible(self, product: FakeProduct) -> bool:
        if product.status != ProductStatus.MODERATED:
            return False
        if product.deleted:
            return False
        if not any(sku.active_quantity > 0 for sku in product.skus):
            return False
        return True

    def _matches_filters(
        self,
        product: FakeProduct,
        *,
        category_id: UUID | None,
        search: str | None,
        min_price: int | None,
        max_price: int | None,
        seller_id: UUID | None,
        filters: dict[str, list[str]] | None,
    ) -> bool:
        if category_id is not None and product.category_id != category_id:
            return False
        if seller_id is not None and product.seller_id != seller_id:
            return False
        if search:
            needle = search.lower()
            if needle not in product.title.lower() and needle not in product.description.lower():
                return False
        active_prices = [sku.price for sku in product.skus if sku.active_quantity > 0]
        if min_price is not None and not any(p >= min_price for p in active_prices):
            return False
        if max_price is not None and not any(p <= max_price for p in active_prices):
            return False
        if filters:
            for name, values in filters.items():
                if not values:
                    continue
                has = any(ch.name == name and ch.value in set(values) for ch in product.characteristics)
                if not has:
                    return False
        return True

    def _with_derived(self, product: FakeProduct) -> FakeProduct:
        product.min_price = _visible_min_price(product)
        product.cover_image = _cover_image(product)
        return product

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
    ) -> tuple[list[FakeProduct], int]:
        matched = [
            p
            for p in self.products
            if self._is_visible(p)
            and self._matches_filters(
                p,
                category_id=category_id,
                search=search,
                min_price=min_price,
                max_price=max_price,
                seller_id=seller_id,
                filters=filters,
            )
        ]
        for product in matched:
            self._with_derived(product)

        if sort == CatalogSort.PRICE_ASC:
            matched.sort(key=lambda p: (p.min_price, str(p.id)))
        elif sort == CatalogSort.PRICE_DESC:
            matched.sort(key=lambda p: (-p.min_price, str(p.id)))
        else:  # created_desc и popular (fallback)
            matched.sort(key=lambda p: (p.created_at, str(p.id)), reverse=True)

        total = len(matched)
        return matched[offset : offset + limit], total

    async def get_full_by_id(self, product_id: UUID) -> FakeProduct | None:
        for product in self.products:
            if product.id == product_id and self._is_visible(product):
                return product
        return None

    async def list_full_by_ids(self, product_ids: list[UUID]) -> list[FakeProduct]:
        wanted = set(product_ids)
        visible = [p for p in self.products if p.id in wanted and self._is_visible(p)]
        visible.sort(key=lambda p: (p.created_at, str(p.id)), reverse=True)
        return visible

    async def list_similar_short(self, product_id: UUID, *, limit: int = 10) -> list[FakeProduct]:
        source = next((p for p in self.products if p.id == product_id), None)
        if source is None:
            return []
        similar = [
            self._with_derived(p)
            for p in self.products
            if p.id != product_id and p.category_id == source.category_id and self._is_visible(p)
        ]
        # Детерминированный порядок в тестах (реальный репозиторий — random).
        similar.sort(key=lambda p: str(p.id))
        return similar[:limit]

    async def aggregate_facets(
        self,
        *,
        category_id: UUID | None = None,
        search: str | None = None,
        min_price: int | None = None,
        max_price: int | None = None,
        seller_id: UUID | None = None,
    ) -> tuple[list[tuple[str, str, int]], tuple[int, int]]:
        """Фейк агрегации фасетов: те же условия видимости/фильтры, что и list_short.

        Возвращает (name, value, count) по характеристикам видимых отфильтрованных
        товаров + диапазон (min, max) минимальной цены SKU.
        """
        matched = [
            p
            for p in self.products
            if self._is_visible(p)
            and self._matches_filters(
                p,
                category_id=category_id,
                search=search,
                min_price=min_price,
                max_price=max_price,
                seller_id=seller_id,
                filters=None,
            )
        ]

        counts: dict[tuple[str, str], int] = {}
        for product in matched:
            for ch in product.characteristics:
                counts[(ch.name, ch.value)] = counts.get((ch.name, ch.value), 0) + 1
        # Порядок как у реального репозитория: по name asc, затем count desc.
        rows = sorted(((name, value, count) for (name, value), count in counts.items()), key=lambda r: (r[0], -r[2]))

        prices = [_visible_min_price(p) for p in matched]
        prices = [price for price in prices if price > 0]
        price_range = (min(prices), max(prices)) if prices else (0, 0)
        return rows, price_range

    async def get_public_sku(self, sku_id: UUID) -> FakeSKU | None:
        for product in self.products:
            for sku in product.skus:
                if sku.id == sku_id:
                    return sku if self._is_visible(product) else None
        return None


# Удобный конструктор изображения/характеристики для тестов.
def make_image(url: str, ordering: int = 0) -> FakeImage:
    return FakeImage(id=uuid4(), url=url, ordering=ordering)


def make_characteristic(name: str, value: str) -> FakeCharacteristic:
    return FakeCharacteristic(id=uuid4(), name=name, value=value)


def past(seconds: int) -> datetime:
    """created_at в прошлом — для детерминированной сортировки по дате."""
    return datetime.now(UTC) - timedelta(seconds=seconds)

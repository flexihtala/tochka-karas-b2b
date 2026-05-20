"""Фейки для tests/public.

Имитируют поведение PublicCatalogRepository, но без БД. Применяют те же
условия видимости (status == MODERATED, deleted == False, есть SKU с
active_quantity > 0) — это позволяет тестировать use-case как против реального
репозитория, так и поверх фейков.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from apps.products.enums import ProductStatus


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
) -> FakeProduct:
    now = datetime.now(UTC)
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
    )


class FakePublicCatalogRepository:
    """Фейк репозитория витрины.

    Внутри держит список FakeProduct (со связанными SKU). `list_visible`
    применяет реальные условия видимости + опциональный фильтр по ids +
    пагинацию.
    """

    def __init__(self) -> None:
        self.products: list[FakeProduct] = []
        self.list_calls: list[tuple[list[UUID] | None, int, int]] = []

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

    async def list_visible(
        self,
        *,
        ids: list[UUID] | None,
        limit: int,
        offset: int,
    ) -> tuple[list[FakeProduct], int]:
        self.list_calls.append((ids, limit, offset))
        visible = [p for p in self.products if self._is_visible(p)]
        if ids is not None:
            visible = [p for p in visible if p.id in set(ids)]
        total = len(visible)
        # Стабильный порядок: сначала более новые. У фейка created_at почти одинаковый,
        # поэтому дополнительно сортируем по id для детерминизма.
        visible.sort(key=lambda p: (p.created_at, str(p.id)), reverse=True)
        return visible[offset : offset + limit], total

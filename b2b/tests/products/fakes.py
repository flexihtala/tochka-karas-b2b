from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from apps.categories.schemas import CategoryCreateSchema, CategoryReadSchema, CategoryUpdateSchema
from apps.products.enums import ProductStatus
from apps.products.repositories import SellerProductRow
from apps.products.schemas.db import (
    CharacteristicValueCreateSchema,
    CharacteristicValueReadSchema,
    ProductCreateSchema,
    ProductImageCreateSchema,
    ProductImageReadSchema,
    ProductReadSchema,
    ProductUpdateSchema,
)
from apps.skus.schemas.db import (
    SKUCharacteristicValueReadSchema,
    SKUImageReadSchema,
    SKUReadSchema,
)
from shared.outbox import OutboxEnqueueSchema


class FakeCategoryRepository:
    def __init__(self):
        self.by_id: dict[UUID, CategoryReadSchema] = {}
        self.created: list[CategoryCreateSchema] = []
        self.updated: list[CategoryUpdateSchema] = []

    def add(self, *, id: UUID | None = None, name: str = 'Электроника', parent_id: UUID | None = None) -> UUID:
        category_id = id or uuid4()
        now = datetime.now(UTC)
        category = CategoryReadSchema(
            id=category_id,
            name=name,
            parent_id=parent_id,
            created_at=now,
            updated_at=now,
        )
        self.by_id[category_id] = category
        return category_id

    async def create(self, data: CategoryCreateSchema) -> CategoryReadSchema:
        self.created.append(data)
        category_id = data.id or uuid4()
        now = datetime.now(UTC)
        category = CategoryReadSchema(
            id=category_id,
            name=data.name,
            parent_id=data.parent_id,
            created_at=now,
            updated_at=now,
        )
        self.by_id[category_id] = category
        return category

    async def get_or_none(self, id_: UUID) -> CategoryReadSchema | None:
        return self.by_id.get(id_)

    async def exists(self, category_id: UUID) -> bool:
        return category_id in self.by_id


class FakeProductRepository:
    def __init__(self):
        self.by_id: dict[UUID, ProductReadSchema] = {}
        self.created: list[ProductCreateSchema] = []
        self.updated: list[ProductUpdateSchema] = []
        # product_id -> (skus_count, total_active_quantity); агрегаты по SKU,
        # которые реальный репозиторий считает подзапросами в list_for_seller.
        self.aggregates: dict[UUID, tuple[int, int]] = {}

    def add(
        self,
        *,
        id: UUID | None = None,
        seller_id: UUID | None = None,
        category_id: UUID | None = None,
        title: str = 'iPhone 15 Pro Max',
        slug: str = 'iphone-15-pro-max',
        description: str = 'Флагман Apple',
        status: ProductStatus = ProductStatus.MODERATED,
        deleted: bool = False,
        blocking_reason_id: UUID | None = None,
        blocking_reason_title: str | None = None,
        moderator_comment: str | None = None,
        field_reports: list[dict[str, Any]] | None = None,
        created_at: datetime | None = None,
        skus_count: int = 0,
        total_active_quantity: int = 0,
    ) -> ProductReadSchema:
        """Посадить уже существующий продукт (используется в get/edit/delete/list-тестах)."""
        product_id = id or uuid4()
        now = created_at or datetime.now(UTC)
        self.aggregates[product_id] = (skus_count, total_active_quantity)
        product = ProductReadSchema(
            id=product_id,
            seller_id=seller_id or uuid4(),
            category_id=category_id or uuid4(),
            title=title,
            slug=slug,
            description=description,
            status=status,
            deleted=deleted,
            blocking_reason_id=blocking_reason_id,
            blocking_reason_title=blocking_reason_title,
            moderator_comment=moderator_comment,
            field_reports=field_reports if field_reports is not None else [],
            created_at=now,
            updated_at=now,
        )
        self.by_id[product_id] = product
        return product

    async def create(self, data: ProductCreateSchema) -> ProductReadSchema:
        self.created.append(data)
        product_id = data.id or uuid4()
        now = datetime.now(UTC)
        product = ProductReadSchema(
            id=product_id,
            seller_id=data.seller_id,
            category_id=data.category_id,
            title=data.title,
            slug=data.slug,
            description=data.description,
            status=data.status,
            deleted=data.deleted,
            blocking_reason_id=data.blocking_reason_id,
            blocking_reason_title=data.blocking_reason_title,
            moderator_comment=data.moderator_comment,
            field_reports=data.field_reports,
            created_at=now,
            updated_at=now,
        )
        self.by_id[product_id] = product
        return product

    async def get_or_none(self, id_: UUID) -> ProductReadSchema | None:
        return self.by_id.get(id_)

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
        rows = [p for p in self.by_id.values() if p.seller_id == seller_id]
        if not include_deleted:
            rows = [p for p in rows if not p.deleted]
        if status is not None:
            rows = [p for p in rows if p.status == status]
        if search:
            needle = search.lower()
            rows = [p for p in rows if needle in p.title.lower()]
        rows.sort(key=lambda p: p.created_at, reverse=True)
        total_count = len(rows)
        page = rows[offset : offset + limit]
        result = [
            SellerProductRow(
                product=p,
                skus_count=self.aggregates.get(p.id, (0, 0))[0],
                total_active_quantity=self.aggregates.get(p.id, (0, 0))[1],
            )
            for p in page
        ]
        return result, total_count

    async def update(self, data: ProductUpdateSchema) -> ProductReadSchema | None:
        self.updated.append(data)
        product = self.by_id.get(data.id)
        if product is None:
            return None
        updates = data.model_dump(exclude_unset=True, exclude={'id'})
        merged = product.model_copy(update=updates)
        self.by_id[data.id] = merged
        return merged

    async def list_by_seller(self, seller_id: UUID, *, include_deleted: bool = False) -> list[ProductReadSchema]:
        rows = [p for p in self.by_id.values() if p.seller_id == seller_id]
        if not include_deleted:
            rows = [p for p in rows if not p.deleted]
        return rows


class FakeSKURepositoryForDelete:
    """Минималистичный SKU-фейк для тестов удаления товара.

    Поддерживает только `list_ids_by_product` — единственный вызов из DeleteProductUseCase.
    """

    def __init__(self):
        self.ids_by_product: dict[UUID, list[UUID]] = {}

    def add_sku(self, product_id: UUID, sku_id: UUID | None = None) -> UUID:
        new_id = sku_id or uuid4()
        self.ids_by_product.setdefault(product_id, []).append(new_id)
        return new_id

    async def list_ids_by_product(self, product_id: UUID) -> list[UUID]:
        return list(self.ids_by_product.get(product_id, []))


class FakeProductImageRepository:
    def __init__(self):
        self.created: list[ProductImageCreateSchema] = []
        self.by_id: dict[UUID, ProductImageReadSchema] = {}

    def add(
        self,
        *,
        product_id: UUID,
        url: str = '/s3/image.jpg',
        ordering: int = 0,
        id: UUID | None = None,
    ) -> ProductImageReadSchema:
        image_id = id or uuid4()
        now = datetime.now(UTC)
        image = ProductImageReadSchema(
            id=image_id,
            product_id=product_id,
            url=url,
            ordering=ordering,
            created_at=now,
            updated_at=now,
        )
        self.by_id[image_id] = image
        return image

    async def create(self, data: ProductImageCreateSchema) -> ProductImageReadSchema:
        self.created.append(data)
        image_id = data.id or uuid4()
        now = datetime.now(UTC)
        image = ProductImageReadSchema(
            id=image_id,
            product_id=data.product_id,
            url=data.url,
            ordering=data.ordering,
            created_at=now,
            updated_at=now,
        )
        self.by_id[image_id] = image
        return image

    async def list_by_product(self, product_id: UUID) -> list[ProductImageReadSchema]:
        return sorted(
            [image for image in self.by_id.values() if image.product_id == product_id],
            key=lambda x: x.ordering,
        )

    async def delete_by_product(self, product_id: UUID) -> int:
        to_delete = [iid for iid, image in self.by_id.items() if image.product_id == product_id]
        for iid in to_delete:
            del self.by_id[iid]
        return len(to_delete)


class FakeCharacteristicValueRepository:
    def __init__(self):
        self.created: list[CharacteristicValueCreateSchema] = []
        self.by_id: dict[UUID, CharacteristicValueReadSchema] = {}

    def add(
        self,
        *,
        product_id: UUID,
        name: str = 'Бренд',
        value: str = 'Apple',
        id: UUID | None = None,
    ) -> CharacteristicValueReadSchema:
        characteristic_id = id or uuid4()
        now = datetime.now(UTC)
        characteristic = CharacteristicValueReadSchema(
            id=characteristic_id,
            product_id=product_id,
            name=name,
            value=value,
            created_at=now,
            updated_at=now,
        )
        self.by_id[characteristic_id] = characteristic
        return characteristic

    async def create(self, data: CharacteristicValueCreateSchema) -> CharacteristicValueReadSchema:
        self.created.append(data)
        characteristic_id = data.id or uuid4()
        now = datetime.now(UTC)
        characteristic = CharacteristicValueReadSchema(
            id=characteristic_id,
            product_id=data.product_id,
            name=data.name,
            value=data.value,
            created_at=now,
            updated_at=now,
        )
        self.by_id[characteristic_id] = characteristic
        return characteristic

    async def list_by_product(self, product_id: UUID) -> list[CharacteristicValueReadSchema]:
        return [c for c in self.by_id.values() if c.product_id == product_id]

    async def delete_by_product(self, product_id: UUID) -> int:
        to_delete = [cid for cid, ch in self.by_id.items() if ch.product_id == product_id]
        for cid in to_delete:
            del self.by_id[cid]
        return len(to_delete)


class FakeSKURepositoryForProducts:
    """Минимальный фейк SKURepository для edit-product-тестов.

    Поддерживает count_by_product (через override) и list_full_by_product
    (по умолчанию пусто — у товаров в этих тестах SKU не заведены).
    """

    def __init__(self):
        self.count_by_product_overrides: dict[UUID, int] = {}

    async def count_by_product(self, product_id: UUID) -> int:
        return self.count_by_product_overrides.get(product_id, 0)

    async def list_full_by_product(self, product_id: UUID) -> list[SKUReadSchema]:
        return []


class FakeSKURepositoryForGet:
    """Фейк SKURepository для get-product-тестов (нужен list_full_by_product)."""

    def __init__(self):
        self.by_id: dict[UUID, SKUReadSchema] = {}

    def add(
        self,
        *,
        product_id: UUID,
        id: UUID | None = None,
        name: str = 'iPhone 15 Pro Max 256GB',
        price: int = 9990000,
        cost_price: int | None = 7000000,
        discount: int = 0,
        article: str | None = 'IP15PM-256',
        active_quantity: int = 5,
        reserved_quantity: int = 2,
    ) -> SKUReadSchema:
        sku_id = id or uuid4()
        now = datetime.now(UTC)
        sku = SKUReadSchema(
            id=sku_id,
            product_id=product_id,
            name=name,
            price=price,
            cost_price=cost_price,
            discount=discount,
            article=article,
            active_quantity=active_quantity,
            reserved_quantity=reserved_quantity,
            stock_quantity=active_quantity + reserved_quantity,
            created_at=now,
            updated_at=now,
        )
        self.by_id[sku_id] = sku
        return sku

    async def list_full_by_product(self, product_id: UUID) -> list[SKUReadSchema]:
        return sorted(
            [sku for sku in self.by_id.values() if sku.product_id == product_id],
            key=lambda s: (s.created_at, str(s.id)),
        )

    async def count_by_product(self, product_id: UUID) -> int:
        return len([sku for sku in self.by_id.values() if sku.product_id == product_id])


class FakeSKUImageRepository:
    """Фейк SKUImageRepository для get-product-тестов (нужен list_by_sku)."""

    def __init__(self):
        self.by_id: dict[UUID, SKUImageReadSchema] = {}

    def add(
        self,
        *,
        sku_id: UUID,
        url: str = '/s3/sku-image.jpg',
        ordering: int = 0,
        id: UUID | None = None,
    ) -> SKUImageReadSchema:
        image_id = id or uuid4()
        now = datetime.now(UTC)
        image = SKUImageReadSchema(
            id=image_id,
            sku_id=sku_id,
            url=url,
            ordering=ordering,
            created_at=now,
            updated_at=now,
        )
        self.by_id[image_id] = image
        return image

    async def list_by_sku(self, sku_id: UUID) -> list[SKUImageReadSchema]:
        return sorted(
            [image for image in self.by_id.values() if image.sku_id == sku_id],
            key=lambda x: x.ordering,
        )


class FakeSKUCharacteristicValueRepository:
    """Фейк SKUCharacteristicValueRepository для get-product-тестов (нужен list_by_sku)."""

    def __init__(self):
        self.by_id: dict[UUID, SKUCharacteristicValueReadSchema] = {}

    def add(
        self,
        *,
        sku_id: UUID,
        name: str = 'Память',
        value: str = '256 ГБ',
        id: UUID | None = None,
    ) -> SKUCharacteristicValueReadSchema:
        characteristic_id = id or uuid4()
        now = datetime.now(UTC)
        characteristic = SKUCharacteristicValueReadSchema(
            id=characteristic_id,
            sku_id=sku_id,
            name=name,
            value=value,
            created_at=now,
            updated_at=now,
        )
        self.by_id[characteristic_id] = characteristic
        return characteristic

    async def list_by_sku(self, sku_id: UUID) -> list[SKUCharacteristicValueReadSchema]:
        return [c for c in self.by_id.values() if c.sku_id == sku_id]


class FakeOutboxRepository:
    """Фейк outbox-репозитория для тестов use-case."""

    def __init__(self):
        self.enqueued: list[OutboxEnqueueSchema] = []

    async def enqueue_in_new_transaction(self, data: OutboxEnqueueSchema) -> Any:
        self.enqueued.append(data)
        return None

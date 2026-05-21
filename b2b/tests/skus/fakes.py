from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from apps.products.enums import ProductStatus
from apps.products.schemas.db import (
    CharacteristicValueReadSchema,
    ProductImageReadSchema,
    ProductReadSchema,
    ProductUpdateSchema,
)
from apps.skus.schemas.db import (
    SKUCharacteristicValueCreateSchema,
    SKUCharacteristicValueReadSchema,
    SKUCreateSchema,
    SKUImageCreateSchema,
    SKUImageReadSchema,
    SKUReadSchema,
    SKUUpdateSchema,
)
from shared.outbox import OutboxEnqueueSchema


class FakeSKURepository:
    def __init__(self):
        self.by_id: dict[UUID, SKUReadSchema] = {}
        self.created: list[SKUCreateSchema] = []
        self.updated: list[SKUUpdateSchema] = []
        self.count_by_product_overrides: dict[UUID, int] = {}

    async def create(self, data: SKUCreateSchema) -> SKUReadSchema:
        self.created.append(data)
        sku_id = data.id or uuid4()
        now = datetime.now(UTC)
        sku = SKUReadSchema(
            id=sku_id,
            product_id=data.product_id,
            name=data.name,
            price=data.price,
            cost_price=data.cost_price,
            discount=data.discount,
            article=data.article,
            active_quantity=data.active_quantity,
            reserved_quantity=data.reserved_quantity,
            stock_quantity=data.active_quantity + data.reserved_quantity,
            created_at=now,
            updated_at=now,
        )
        self.by_id[sku_id] = sku
        return sku

    async def get_or_none(self, id_: UUID) -> SKUReadSchema | None:
        return self.by_id.get(id_)

    async def count_by_product(self, product_id: UUID) -> int:
        if product_id in self.count_by_product_overrides:
            return self.count_by_product_overrides[product_id]
        return sum(1 for s in self.by_id.values() if s.product_id == product_id)


class FakeSKUImageRepository:
    def __init__(self):
        self.created: list[SKUImageCreateSchema] = []
        self.by_id: dict[UUID, SKUImageReadSchema] = {}

    async def create(self, data: SKUImageCreateSchema) -> SKUImageReadSchema:
        self.created.append(data)
        image_id = data.id or uuid4()
        now = datetime.now(UTC)
        image = SKUImageReadSchema(
            id=image_id,
            sku_id=data.sku_id,
            url=data.url,
            ordering=data.ordering,
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
    def __init__(self):
        self.created: list[SKUCharacteristicValueCreateSchema] = []
        self.by_id: dict[UUID, SKUCharacteristicValueReadSchema] = {}

    async def create(self, data: SKUCharacteristicValueCreateSchema) -> SKUCharacteristicValueReadSchema:
        self.created.append(data)
        characteristic_id = data.id or uuid4()
        now = datetime.now(UTC)
        characteristic = SKUCharacteristicValueReadSchema(
            id=characteristic_id,
            sku_id=data.sku_id,
            name=data.name,
            value=data.value,
            created_at=now,
            updated_at=now,
        )
        self.by_id[characteristic_id] = characteristic
        return characteristic

    async def list_by_sku(self, sku_id: UUID) -> list[SKUCharacteristicValueReadSchema]:
        return [c for c in self.by_id.values() if c.sku_id == sku_id]


class FakeProductRepositoryReadable:
    """Read-only fake продуктов для тестов SKU: get_or_none + update (для смены статуса)."""

    def __init__(self):
        self.by_id: dict[UUID, ProductReadSchema] = {}
        self.updated: list[ProductUpdateSchema] = []

    def add(
        self,
        *,
        id: UUID | None = None,
        seller_id: UUID | None = None,
        category_id: UUID | None = None,
        title: str = 'iPhone 15 Pro Max',
        slug: str = 'iphone-15-pro-max',
        description: str = 'Флагман Apple',
        status: ProductStatus = ProductStatus.CREATED,
        deleted: bool = False,
    ) -> UUID:
        product_id = id or uuid4()
        now = datetime.now(UTC)
        product = ProductReadSchema(
            id=product_id,
            seller_id=seller_id or uuid4(),
            category_id=category_id or uuid4(),
            title=title,
            slug=slug,
            description=description,
            status=status,
            deleted=deleted,
            blocking_reason_id=None,
            moderator_comment=None,
            created_at=now,
            updated_at=now,
        )
        self.by_id[product_id] = product
        return product_id

    async def get_or_none(self, id_: UUID) -> ProductReadSchema | None:
        return self.by_id.get(id_)

    async def update(self, data: ProductUpdateSchema) -> ProductReadSchema | None:
        self.updated.append(data)
        product = self.by_id.get(data.id)
        if product is None:
            return None
        updates = data.model_dump(exclude_unset=True, exclude={'id'})
        merged = product.model_copy(update=updates)
        self.by_id[data.id] = merged
        return merged


class FakeProductImageRepository:
    def __init__(self):
        self.by_id: dict[UUID, ProductImageReadSchema] = {}

    def add(self, *, product_id: UUID, url: str, ordering: int = 0) -> UUID:
        image_id = uuid4()
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
        return image_id

    async def list_by_product(self, product_id: UUID) -> list[ProductImageReadSchema]:
        return sorted(
            [image for image in self.by_id.values() if image.product_id == product_id],
            key=lambda x: x.ordering,
        )


class FakeProductCharacteristicRepository:
    def __init__(self):
        self.by_id: dict[UUID, CharacteristicValueReadSchema] = {}

    def add(self, *, product_id: UUID, name: str, value: str) -> UUID:
        ch_id = uuid4()
        now = datetime.now(UTC)
        ch = CharacteristicValueReadSchema(
            id=ch_id,
            product_id=product_id,
            name=name,
            value=value,
            created_at=now,
            updated_at=now,
        )
        self.by_id[ch_id] = ch
        return ch_id

    async def list_by_product(self, product_id: UUID) -> list[CharacteristicValueReadSchema]:
        return [c for c in self.by_id.values() if c.product_id == product_id]


class FakeOutboxRepository:
    """Фейк b2b outbox-репозитория. Захватывает enqueue-вызовы для assertions."""

    def __init__(self):
        self.enqueued: list[OutboxEnqueueSchema] = []

    async def enqueue_in_new_transaction(self, data: OutboxEnqueueSchema) -> Any:
        self.enqueued.append(data)
        return None

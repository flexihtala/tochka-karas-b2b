from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from apps.categories.schemas import CategoryCreateSchema, CategoryReadSchema, CategoryUpdateSchema
from apps.products.enums import ProductStatus
from apps.products.schemas.db import (
    CharacteristicValueCreateSchema,
    CharacteristicValueReadSchema,
    ProductCreateSchema,
    ProductImageCreateSchema,
    ProductImageReadSchema,
    ProductReadSchema,
    ProductUpdateSchema,
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
        """Используется в edit-тестах: посадить уже существующий продукт."""
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
            moderator_comment=data.moderator_comment,
            created_at=now,
            updated_at=now,
        )
        self.by_id[product_id] = product
        return product

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
        self.created: list[ProductImageCreateSchema] = []
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
    """Минимальный фейк SKURepository для edit-product-тестов (нужен count_by_product)."""

    def __init__(self):
        self.count_by_product_overrides: dict[UUID, int] = {}

    async def count_by_product(self, product_id: UUID) -> int:
        return self.count_by_product_overrides.get(product_id, 0)


class FakeOutboxRepository:
    """Фейк outbox-репозитория для тестов use-case."""

    def __init__(self):
        self.enqueued: list[OutboxEnqueueSchema] = []

    async def enqueue_in_new_transaction(self, data: OutboxEnqueueSchema) -> Any:
        self.enqueued.append(data)
        return None

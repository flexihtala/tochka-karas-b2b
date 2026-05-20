from datetime import UTC, datetime
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
)


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

    def add(
        self,
        *,
        seller_id: UUID,
        title: str = 'iPhone 15 Pro Max',
        slug: str | None = None,
        description: str = 'Флагман Apple',
        category_id: UUID | None = None,
        status: ProductStatus = ProductStatus.CREATED,
        deleted: bool = False,
        created_at: datetime | None = None,
    ) -> ProductReadSchema:
        product_id = uuid4()
        now = created_at or datetime.now(UTC)
        product = ProductReadSchema(
            id=product_id,
            seller_id=seller_id,
            category_id=category_id or uuid4(),
            title=title,
            slug=slug or f'slug-{product_id.hex[:8]}',
            description=description,
            status=status,
            deleted=deleted,
            blocking_reason_id=None,
            moderator_comment=None,
            created_at=now,
            updated_at=now,
        )
        self.by_id[product_id] = product
        return product

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
        return rows[offset : offset + limit], total_count


class FakeProductImageRepository:
    def __init__(self):
        self.created: list[ProductImageCreateSchema] = []
        self.by_id: dict[UUID, ProductImageReadSchema] = {}

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


class FakeCharacteristicValueRepository:
    def __init__(self):
        self.created: list[CharacteristicValueCreateSchema] = []
        self.by_id: dict[UUID, CharacteristicValueReadSchema] = {}

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

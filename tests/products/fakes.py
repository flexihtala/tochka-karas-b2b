from datetime import UTC, datetime
from uuid import UUID, uuid4

from apps.products.schemas.category import CategoryReadSchema
from apps.products.schemas.product import (
    ProductCharacteristicReadSchema,
    ProductCreateSchema,
    ProductImageReadSchema,
    ProductReadSchema,
)


class FakeCategoryRepository:
    def __init__(self):
        self.categories: dict[UUID, CategoryReadSchema] = {}

    async def get_or_none(self, id_: UUID) -> CategoryReadSchema | None:
        return self.categories.get(id_)

    def add(self, category: CategoryReadSchema) -> None:
        self.categories[category.id] = category


class FakeProductRepository:
    def __init__(self):
        self.created_product: ProductCreateSchema | None = None
        self.created_read_product: ProductReadSchema | None = None

    async def create(self, data: ProductCreateSchema) -> ProductReadSchema:
        self.created_product = data
        now = datetime.now(UTC)
        product_id = data.id or uuid4()
        self.created_read_product = ProductReadSchema(
            id=product_id,
            seller_id=data.seller_id,
            title=data.title,
            description=data.description,
            status=data.status,
            deleted=data.deleted,
            blocked=data.blocked,
            category_id=data.category_id,
            created_at=now,
            updated_at=now,
        )
        return self.created_read_product


class FakeProductImageRepository:
    def __init__(self):
        self.created_images: list[ProductImageReadSchema] = []

    async def create(self, data) -> ProductImageReadSchema:
        image = ProductImageReadSchema(
            id=data.id or uuid4(),
            product_id=data.product_id,
            url=data.url,
            ordering=data.ordering,
        )
        self.created_images.append(image)
        return image


class FakeProductCharacteristicRepository:
    def __init__(self):
        self.created_characteristics: list[ProductCharacteristicReadSchema] = []

    async def create(self, data) -> ProductCharacteristicReadSchema:
        characteristic = ProductCharacteristicReadSchema(
            id=data.id or uuid4(),
            product_id=data.product_id,
            name=data.name,
            value=data.value,
        )
        self.created_characteristics.append(characteristic)
        return characteristic

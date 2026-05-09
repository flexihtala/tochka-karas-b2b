from datetime import UTC, datetime
from uuid import UUID, uuid4

from apps.products.schemas.category import CategoryReadSchema
from apps.products.schemas.product import (
    ProductCharacteristicReadSchema,
    ProductCreateSchema,
    ProductImageReadSchema,
    ProductReadSchema,
    ProductUpdateSchema,
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
        self.products: dict[UUID, ProductReadSchema] = {}
        self.updated_products: list[ProductUpdateSchema] = []

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
        self.products[self.created_read_product.id] = self.created_read_product
        return self.created_read_product

    def add(self, product: ProductReadSchema) -> None:
        self.products[product.id] = product

    async def get_or_none(self, id_: UUID) -> ProductReadSchema | None:
        return self.products.get(id_)

    async def update(self, data: ProductUpdateSchema) -> ProductReadSchema | None:
        self.updated_products.append(data)
        product = self.products.get(data.id)
        if product is None:
            return None
        update_values = data.model_dump(exclude_unset=True, exclude={'id'})
        updated = product.model_copy(update={**update_values, 'updated_at': datetime.now(UTC)})
        self.products[data.id] = updated
        return updated


class FakeProductImageRepository:
    def __init__(self):
        self.created_images: list[ProductImageReadSchema] = []
        self.deleted_for: list[UUID] = []

    async def create(self, data) -> ProductImageReadSchema:
        image = ProductImageReadSchema(
            id=data.id or uuid4(),
            product_id=data.product_id,
            url=data.url,
            ordering=data.ordering,
        )
        self.created_images.append(image)
        return image

    async def delete_by_product_id(self, product_id: UUID) -> None:
        self.deleted_for.append(product_id)
        self.created_images = [image for image in self.created_images if image.product_id != product_id]


class FakeProductCharacteristicRepository:
    def __init__(self):
        self.created_characteristics: list[ProductCharacteristicReadSchema] = []
        self.deleted_for: list[UUID] = []

    async def create(self, data) -> ProductCharacteristicReadSchema:
        characteristic = ProductCharacteristicReadSchema(
            id=data.id or uuid4(),
            product_id=data.product_id,
            name=data.name,
            value=data.value,
        )
        self.created_characteristics.append(characteristic)
        return characteristic

    async def delete_by_product_id(self, product_id: UUID) -> None:
        self.deleted_for.append(product_id)
        self.created_characteristics = [
            characteristic for characteristic in self.created_characteristics if characteristic.product_id != product_id
        ]

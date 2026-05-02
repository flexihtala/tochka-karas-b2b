from uuid import UUID, uuid4

from apps.products.schemas.category import CategoryReadSchema
from apps.products.schemas.product import ProductCreateSchema, ProductReadSchema


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

    async def create(self, data: ProductCreateSchema) -> ProductReadSchema:
        self.created_product = data
        return ProductReadSchema(
            id=data.id or uuid4(),
            seller_id=data.seller_id,
            title=data.title,
            description=data.description,
            status=data.status,
            deleted=data.deleted,
            blocked=data.blocked,
            category_id=data.category_id,
            images=data.images,
            characteristics=data.characteristics,
        )

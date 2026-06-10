from uuid import UUID

from apps.home.errors import CollectionNotFoundError
from apps.home.repositories import CollectionItemRepository, CollectionRepository
from apps.home.schemas.response import (
    CollectionProductItemSchema,
    CollectionProductsResponseSchema,
)
from apps.home.services import B2BProductsClient


class GetCollectionProductsUseCase:
    """GET /home/collections/{id}/products — обогащённые товары подборки.

    Алгоритм:
    1. Подборка не существует → 404.
    2. Получить список product_id из b2c.collection_items (упорядочено по `ordering`).
    3. Пакетно запросить b2b → доступные товары.
    4. items — в исходном порядке `ordering`, недостающие id → unavailable_ids.
    5. Пустая подборка → `{items: [], unavailable_ids: []}` (статус 200).
    """

    def __init__(
        self,
        collection_repository: CollectionRepository,
        collection_item_repository: CollectionItemRepository,
        b2b_products_client: B2BProductsClient,
    ):
        self.collection_repository = collection_repository
        self.collection_item_repository = collection_item_repository
        self.b2b_products_client = b2b_products_client

    async def __call__(self, collection_id: UUID) -> CollectionProductsResponseSchema:
        collection = await self.collection_repository.get_or_none(collection_id)
        if collection is None:
            raise CollectionNotFoundError()

        items = await self.collection_item_repository.list_by_collection(collection_id)
        product_ids: list[UUID] = [it.product_id for it in items]

        if not product_ids:
            return CollectionProductsResponseSchema(items=[], unavailable_ids=[])

        b2b_products = await self.b2b_products_client.fetch_batch(product_ids)
        available_by_id = {p.id: p for p in b2b_products}

        ordered_items: list[CollectionProductItemSchema] = []
        unavailable_ids: list[UUID] = []
        for pid in product_ids:
            product = available_by_id.get(pid)
            if product is None:
                unavailable_ids.append(pid)
                continue
            ordered_items.append(
                CollectionProductItemSchema(
                    id=product.id,
                    title=product.title,
                    slug=product.slug,
                    price=product.price,
                    image_url=product.image_url,
                )
            )

        return CollectionProductsResponseSchema(items=ordered_items, unavailable_ids=unavailable_ids)

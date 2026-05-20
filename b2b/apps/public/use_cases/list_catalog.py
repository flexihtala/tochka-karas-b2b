"""US-B2B-07: каталог для B2C через X-Service-Key.

Бизнес-правила (см. neomarket-canon/flows/b2b-flows.md#catalog-for-b2c):

- Условие видимости товара (все одновременно):
    * status == MODERATED
    * deleted == false
    * хотя бы один SKU с active_quantity > 0
  HARD_BLOCKED товары технически отфильтрованы условием status == MODERATED,
  но мы фиксируем его явно — спецификация требует.

- Аутентификация: только X-Service-Key с направлением b2c_to_b2b. NO JWT.

- Response НЕ содержит cost_price и reserved_quantity — это поля только seller-view.

- Batch (?ids=uuid1,uuid2): возвращаем подмножество видимых. Отсутствующие/скрытые
  товары просто НЕ попадают в выдачу (НЕ 404), B2C интерпретирует их как unavailable.

- Пагинация: limit / offset, по умолчанию (20, 0).
"""

from typing import Protocol
from uuid import UUID

from apps.public.schemas.response import (
    CharacteristicPublicResponseSchema,
    ProductImagePublicResponseSchema,
    ProductPublicPaginatedResponseSchema,
    ProductPublicResponseSchema,
    SKUImagePublicResponseSchema,
    SKUPublicResponseSchema,
)


class _ProductSnapshot(Protocol):
    """Сырой read-only снимок продукта со всеми связями — используется репозиторием."""

    id: UUID
    seller_id: UUID
    category_id: UUID
    title: str
    slug: str
    description: str
    status: object  # ProductStatus, но Protocol не требует точного типа
    images: list
    characteristics: list
    skus: list
    created_at: object
    updated_at: object


class PublicCatalogRepositoryProtocol(Protocol):
    """Интерфейс репозитория витрины. Реализация — в репозитории на стороне infra."""

    async def list_visible(
        self,
        *,
        ids: list[UUID] | None,
        limit: int,
        offset: int,
    ) -> tuple[list[_ProductSnapshot], int]:
        """Список товаров, удовлетворяющих условиям видимости + total_count.

        Аргументы:
            ids: при не-None — фильтрация по конкретному списку product_id (batch).
                 Пустой список → пустая выдача.
            limit, offset: пагинация.
        """
        ...


class ListCatalogUseCase:
    """US-B2B-07: листинг каталога для B2C."""

    def __init__(self, repository: PublicCatalogRepositoryProtocol):
        self.repository = repository

    async def __call__(
        self,
        *,
        ids: list[UUID] | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> ProductPublicPaginatedResponseSchema:
        # batch с пустым списком — короткий путь: возвращаем пусто без запроса в БД.
        if ids is not None and len(ids) == 0:
            return ProductPublicPaginatedResponseSchema(
                items=[],
                total_count=0,
                limit=limit,
                offset=offset,
            )

        items, total = await self.repository.list_visible(ids=ids, limit=limit, offset=offset)

        return ProductPublicPaginatedResponseSchema(
            items=[self._to_response(product) for product in items],
            total_count=total,
            limit=limit,
            offset=offset,
        )

    @staticmethod
    def _to_response(product: _ProductSnapshot) -> ProductPublicResponseSchema:
        return ProductPublicResponseSchema(
            id=product.id,
            seller_id=product.seller_id,
            category_id=product.category_id,
            title=product.title,
            slug=product.slug,
            description=product.description,
            status=product.status,
            images=[
                ProductImagePublicResponseSchema(id=image.id, url=image.url, ordering=image.ordering)
                for image in product.images
            ],
            characteristics=[
                CharacteristicPublicResponseSchema(id=ch.id, name=ch.name, value=ch.value)
                for ch in product.characteristics
            ],
            skus=[
                SKUPublicResponseSchema(
                    id=sku.id,
                    product_id=sku.product_id,
                    name=sku.name,
                    price=sku.price,
                    discount=sku.discount,
                    active_quantity=sku.active_quantity,
                    article=sku.article,
                    images=[
                        SKUImagePublicResponseSchema(id=img.id, url=img.url, ordering=img.ordering)
                        for img in sku.images
                    ],
                    characteristics=[
                        CharacteristicPublicResponseSchema(id=ch.id, name=ch.name, value=ch.value)
                        for ch in sku.characteristics
                    ],
                )
                for sku in product.skus
            ],
            created_at=product.created_at,
            updated_at=product.updated_at,
        )

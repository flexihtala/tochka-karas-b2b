"""US-B2B-07: каталог для B2C через X-Service-Key — листинг коротких карточек.

Бизнес-правила (см. neomarket-canon/flows/b2b-flows.md#catalog-for-b2c + OpenAPI):

- Условие видимости товара (все одновременно):
    * status == MODERATED
    * deleted == false
    * хотя бы один SKU с active_quantity > 0
  HARD_BLOCKED товары технически отфильтрованы условием status == MODERATED.

- Аутентификация: только X-Service-Key с направлением b2c_to_b2b. NO JWT.

- Листинг возвращает КОРОТКИЕ карточки (ProductPublicShortResponse): без skus,
  но с min_price (мин. цена видимых SKU) и cover_image.

- Фильтры: category_id, search, min_price, max_price, seller_id, filters[...]
  (по характеристикам), sort. Пагинация: limit / offset.
"""

from typing import Protocol
from uuid import UUID

from apps.public.enums import CatalogSort
from apps.public.schemas.response import ProductPublicPaginatedResponseSchema
from apps.public.use_cases.mappers import to_short_response


class PublicCatalogRepositoryProtocol(Protocol):
    """Интерфейс репозитория витрины. Реализация — в catalog_repository.py."""

    async def list_short(
        self,
        *,
        category_id: UUID | None = None,
        search: str | None = None,
        min_price: int | None = None,
        max_price: int | None = None,
        seller_id: UUID | None = None,
        filters: dict[str, list[str]] | None = None,
        sort: CatalogSort = CatalogSort.CREATED_DESC,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list, int]: ...


class ListCatalogUseCase:
    """US-B2B-07: листинг каталога для B2C (короткие карточки)."""

    def __init__(self, repository: PublicCatalogRepositoryProtocol):
        self.repository = repository

    async def __call__(
        self,
        *,
        category_id: UUID | None = None,
        search: str | None = None,
        min_price: int | None = None,
        max_price: int | None = None,
        seller_id: UUID | None = None,
        filters: dict[str, list[str]] | None = None,
        sort: CatalogSort = CatalogSort.CREATED_DESC,
        limit: int = 20,
        offset: int = 0,
    ) -> ProductPublicPaginatedResponseSchema:
        items, total = await self.repository.list_short(
            category_id=category_id,
            search=search,
            min_price=min_price,
            max_price=max_price,
            seller_id=seller_id,
            filters=filters,
            sort=sort,
            limit=limit,
            offset=offset,
        )
        return ProductPublicPaginatedResponseSchema(
            items=[to_short_response(product) for product in items],
            total_count=total,
            limit=limit,
            offset=offset,
        )

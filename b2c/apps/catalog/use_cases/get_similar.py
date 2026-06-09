"""US-CAT-04: GET /api/v1/products/{id}/similar — похожие товары.

Проксирует к B2B `/api/v1/public/products/{id}/similar` и маппит ответ
(ProductPublicShortResponse) в B2C CatalogProductCard. Алгоритм подбора
(рандом из той же категории, fallback на родительскую) живёт на B2B-стороне.

ADR (алгоритм подбора): ORDER BY RANDOM() / by characteristic match / cache.

Выбор: **ORDER BY RANDOM()** (на стороне B2B) — на MVP. Критерии:
- MVP-complexity: тривиальная имплементация, никаких ML/индексов.
- Consistency: каждый запрос — независимая выборка из текущих видимых товаров,
  никакой stale-cache. Если товар уехал из продажи — он сразу пропадает.

B2C просто проксирует — внутреннее устройство выборки B2B нам прозрачно.
"""

from typing import Any
from uuid import UUID

from apps.catalog.clients import B2BCatalogClient
from apps.catalog.errors import CatalogUnavailableError, ProductNotFoundError
from apps.catalog.schemas.response import (
    CatalogPaginatedResponseSchema,
    CatalogProductCardSchema,
    ImageRefSchema,
)
from shared.http_clients import ServiceClientError


class GetSimilarUseCase:
    """GET /api/v1/products/{id}/similar — похожие товары."""

    DEFAULT_LIMIT = 8
    MAX_LIMIT = 20

    def __init__(self, b2b_client: B2BCatalogClient):
        self.b2b_client = b2b_client

    async def __call__(
        self,
        product_id: UUID,
        *,
        limit: int = DEFAULT_LIMIT,
        offset: int = 0,
    ) -> CatalogPaginatedResponseSchema:
        limit = max(1, min(limit, self.MAX_LIMIT))
        offset = max(0, offset)
        params: dict[str, Any] = {'limit': limit, 'offset': offset}

        try:
            payload = await self.b2b_client.get_similar(product_id, params)
        except ServiceClientError as exc:
            if exc.status_code == 404:
                raise ProductNotFoundError() from exc
            if exc.status_code >= 500:
                raise CatalogUnavailableError() from exc
            raise
        except Exception as exc:
            raise CatalogUnavailableError() from exc

        # B2B может вернуть {items:[...]} или просто [...] — поддерживаем оба.
        if isinstance(payload, list):
            items_payload = payload
            total_count = len(payload)
        else:
            items_payload = payload.get('items') or []
            total_count = int(payload.get('total_count', len(items_payload)) or 0)

        # Маппинг B2B ProductPublicShortResponse → B2C CatalogProductCard
        # (как в ListProductsUseCase): name←title, images←[cover_image], has_stock←true
        # (B2B-выдача содержит только товары в наличии).
        items: list[CatalogProductCardSchema] = []
        for item in items_payload:
            cover_image = item.get('cover_image')
            images: list[ImageRefSchema] = []
            if cover_image:
                images = [ImageRefSchema(id=item['id'], url=cover_image, ordering=0, is_main=True)]
            items.append(
                CatalogProductCardSchema(
                    id=item['id'],
                    name=item.get('title') or item.get('name') or '',
                    slug=item.get('slug'),
                    min_price=int(item.get('min_price', 0) or 0),
                    has_stock=True,
                    images=images,
                )
            )

        return CatalogPaginatedResponseSchema(
            items=items,
            total_count=total_count,
            limit=limit,
            offset=offset,
        )

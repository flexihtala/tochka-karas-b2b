"""US-CAT-04: GET /api/v1/products/{id}/similar — похожие товары.

Проксирует к B2B `/api/v1/catalog/products/{id}/similar`. Алгоритм подбора
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
from apps.catalog.schemas.response import CatalogPaginatedResponseSchema
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

        # Нормализация: если B2B вернул пустой { items: [] } или просто [] —
        # обрабатываем оба варианта.
        if isinstance(payload, list):
            payload = {'items': payload, 'total_count': len(payload), 'limit': limit, 'offset': offset}
        payload.setdefault('total_count', len(payload.get('items', [])))
        payload.setdefault('limit', limit)
        payload.setdefault('offset', offset)

        return CatalogPaginatedResponseSchema.model_validate(payload)

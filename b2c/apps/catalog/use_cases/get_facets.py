"""US-CAT-01: GET /api/v1/catalog/facets — фасеты с подсчётом.

Проксирует запрос в B2B `/api/v1/catalog/facets`. B2B решает, как считать
фасеты (через SQL GROUP BY либо кэш — это его внутренняя деталь).
"""

from typing import Any
from uuid import UUID

from apps.catalog.clients import B2BCatalogClient
from apps.catalog.errors import CatalogUnavailableError
from apps.catalog.schemas.response import CatalogFacetsResponseSchema
from shared.http_clients import ServiceClientError


class GetFacetsUseCase:
    """GET /api/v1/catalog/facets — фасеты по текущему набору фильтров."""

    def __init__(self, b2b_client: B2BCatalogClient):
        self.b2b_client = b2b_client

    async def __call__(
        self,
        *,
        category_id: UUID | None = None,
        price_min: int | None = None,
        price_max: int | None = None,
    ) -> CatalogFacetsResponseSchema:
        params: dict[str, Any] = {}
        if category_id is not None:
            params['category_id'] = str(category_id)
        if price_min is not None:
            params['price_min'] = price_min
        if price_max is not None:
            params['price_max'] = price_max

        try:
            payload = await self.b2b_client.get_facets(params)
        except ServiceClientError as exc:
            if exc.status_code >= 500:
                raise CatalogUnavailableError() from exc
            raise
        except Exception as exc:
            raise CatalogUnavailableError() from exc

        return CatalogFacetsResponseSchema.model_validate(payload)

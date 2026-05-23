"""HTTP-клиент к B2B catalog endpoints.

Тонкая обёртка над shared.http_clients.ServiceClient — добавляет конкретные
методы каталога, чтобы use-cases не возились с путями/именами параметров.
"""

from typing import Any
from uuid import UUID

from shared.http_clients import ServiceClient


class B2BCatalogClient:
    """Клиент к B2B catalog API.

    Все ошибки uplevel — пробрасываем ServiceClientError, use-case переводит в
    CatalogUnavailableError при сетевых сбоях / 5xx от B2B.
    """

    def __init__(self, service_client: ServiceClient):
        self.client = service_client

    async def list_products(self, params: dict[str, Any]) -> dict[str, Any]:
        """GET /api/v1/catalog/products — листинг с фильтрами/сортировкой/поиском."""
        return await self.client.get('/api/v1/catalog/products', params=params)

    async def get_facets(self, params: dict[str, Any]) -> dict[str, Any]:
        """GET /api/v1/catalog/facets — фасеты с подсчётом по текущим фильтрам."""
        return await self.client.get('/api/v1/catalog/facets', params=params)

    async def get_product(self, product_id: UUID) -> dict[str, Any]:
        """GET /api/v1/catalog/products/{id} — карточка товара (B2C view)."""
        return await self.client.get(f'/api/v1/catalog/products/{product_id}')

    async def get_similar(self, product_id: UUID, params: dict[str, Any]) -> dict[str, Any]:
        """GET /api/v1/catalog/products/{id}/similar — похожие товары."""
        return await self.client.get(f'/api/v1/catalog/products/{product_id}/similar', params=params)

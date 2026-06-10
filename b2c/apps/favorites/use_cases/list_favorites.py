from typing import Any
from uuid import UUID

from apps.favorites.errors import B2BUnavailableError
from apps.favorites.repositories import FavoriteRepository
from apps.favorites.schemas.response import (
    FavoriteListResponseSchema,
    FavoriteProductSchema,
)
from shared.auth_lib import AuthenticatedUserSchema
from shared.http_clients import ServiceClient, ServiceClientError


class B2BProductsClient:
    """Тонкая обёртка над ServiceClient для batch-чтения продуктов из B2B.

    Выделена в отдельный класс с одним публичным методом, чтобы в тестах
    подменять через MockTransport на httpx уровне, без моков ServiceClient.
    """

    def __init__(self, service_client: ServiceClient):
        self.service_client = service_client

    async def list_products_by_ids(self, ids: list[UUID]) -> list[dict[str, Any]]:
        """Возвращает только те товары, что вернул B2B (заблокированные/удалённые опускаются).

        B2B-эндпоинт: GET /api/v1/products?ids=<csv>. Ответ — {"items": [...]}.
        """
        if not ids:
            return []
        params = {'ids': ','.join(str(item) for item in ids)}
        try:
            payload = await self.service_client.get('/api/v1/products', params=params)
        except ServiceClientError as exc:
            raise B2BUnavailableError() from exc

        items = payload.get('items', [])
        if not isinstance(items, list):
            return []
        return [item for item in items if isinstance(item, dict)]


class ListFavoritesUseCase:
    """GET /api/v1/favorites — список избранного, обогащённый данными B2B.

    Бизнес-правила:
    - user_id из JWT (current_user.id).
    - Batch-fetch актуальных Product у B2B через ServiceClient.
    - Заблокированные/удалённые товары исключаются: B2B их не возвращает.
    """

    def __init__(
        self,
        favorite_repository: FavoriteRepository,
        b2b_products_client: B2BProductsClient,
    ):
        self.favorite_repository = favorite_repository
        self.b2b_products_client = b2b_products_client

    async def __call__(self, current_user: AuthenticatedUserSchema) -> FavoriteListResponseSchema:
        favorites = await self.favorite_repository.list_by_user(current_user.id)
        if not favorites:
            return FavoriteListResponseSchema(items=[], total=0)

        product_ids = [favorite.product_id for favorite in favorites]
        products = await self.b2b_products_client.list_products_by_ids(product_ids)
        products_by_id = {self._product_id(item): item for item in products if self._product_id(item)}

        items: list[FavoriteProductSchema] = []
        for favorite in favorites:
            product = products_by_id.get(str(favorite.product_id))
            if product is None:
                # B2B не вернул товар => он заблокирован/удалён — исключаем из списка.
                continue
            items.append(
                FavoriteProductSchema(
                    favorite_id=favorite.id,
                    product_id=favorite.product_id,
                    created_at=favorite.created_at,
                    product=product,
                )
            )

        return FavoriteListResponseSchema(items=items, total=len(items))

    @staticmethod
    def _product_id(product: dict[str, Any]) -> str | None:
        raw = product.get('id')
        return str(raw) if raw is not None else None

import logging
from typing import Any
from uuid import UUID

from apps.catalog.schemas import CatalogPaginatedResponseSchema, CatalogProductCardSchema
from apps.catalog.schemas.response import ImageRefSchema
from apps.favorites.repositories import FavoriteRepository
from shared.auth_lib import AuthenticatedUserSchema
from shared.http_clients import ServiceClient, ServiceClientError

logger = logging.getLogger(__name__)


class B2BProductsClient:
    """Тонкая обёртка над ServiceClient для batch-чтения продуктов из B2B.

    Выделена в отдельный класс с одним публичным методом, чтобы в тестах
    подменять через MockTransport на httpx уровне, без моков ServiceClient.

    Транспортные ошибки (ServiceClientError) пробрасываются как есть:
    интерпретация (503 на PUT vs деградация списка на GET) — дело use-case'ов.
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
        payload = await self.service_client.get('/api/v1/products', params=params)

        items = payload.get('items', [])
        if not isinstance(items, list):
            return []
        return [item for item in items if isinstance(item, dict)]


class ListFavoritesUseCase:
    """GET /api/v1/favorites — пагинированный список избранного в формате PaginatedCatalogProducts.

    Бизнес-правила:
    - user_id из JWT (current_user.id).
    - total_count — ОБЩЕЕ число избранного пользователя (до обогащения B2B).
    - Пагинация limit/offset на уровне use-case; batch в B2B уходит только по странице.
    - Заблокированные/удалённые товары исключаются из items: B2B их не возвращает.
    - Деградация: если batch-вызов B2B упал (ServiceClientError) — НЕ 5xx, а 200
      с исключением необогащённых товаров из items (полный отказ → items: []).
    """

    DEFAULT_LIMIT = 20

    def __init__(
        self,
        favorite_repository: FavoriteRepository,
        b2b_products_client: B2BProductsClient,
    ):
        self.favorite_repository = favorite_repository
        self.b2b_products_client = b2b_products_client

    async def __call__(
        self,
        current_user: AuthenticatedUserSchema,
        *,
        limit: int = DEFAULT_LIMIT,
        offset: int = 0,
    ) -> CatalogPaginatedResponseSchema:
        favorites = await self.favorite_repository.list_by_user(current_user.id)
        total_count = len(favorites)
        page = favorites[offset : offset + limit]
        if not page:
            return CatalogPaginatedResponseSchema(items=[], total_count=total_count, limit=limit, offset=offset)

        product_ids = [favorite.product_id for favorite in page]
        try:
            products = await self.b2b_products_client.list_products_by_ids(product_ids)
        except ServiceClientError as exc:
            # Деградация (US-CART-01): B2B недоступен — отдаём 200 без обогащённых
            # карточек; total_count сохраняет реальное число избранного.
            logger.warning('B2B batch enrich failed, degrading favorites list: %s', exc)
            products = []

        products_by_id = {self._product_id(item): item for item in products if self._product_id(item)}

        items: list[CatalogProductCardSchema] = []
        for favorite in page:
            product = products_by_id.get(str(favorite.product_id))
            if product is None:
                # B2B не вернул товар => он заблокирован/удалён (или batch упал) — исключаем.
                continue
            items.append(self._to_card(product))

        return CatalogPaginatedResponseSchema(items=items, total_count=total_count, limit=limit, offset=offset)

    @staticmethod
    def _to_card(item: dict[str, Any]) -> CatalogProductCardSchema:
        """Маппит B2B ProductPublicShort-payload → B2C CatalogProductCard.

        Зеркалирует ListProductsUseCase._to_response (apps/catalog/use_cases/list_products.py):
            name       ← title
            min_price  ← min_price
            has_stock  ← true (B2B отдаёт только видимые товары)
            images     ← [{id, url: cover_image, ordering: 0}] если cover_image, иначе []
            slug       ← slug

        У короткой карточки B2B нет отдельной сущности изображения с собственным id,
        поэтому для единственной обложки используем id товара как стабильный id картинки.
        """
        cover_image = item.get('cover_image')
        images: list[ImageRefSchema] = []
        if cover_image:
            images = [ImageRefSchema(id=item['id'], url=cover_image, ordering=0, is_main=True)]
        return CatalogProductCardSchema(
            id=item['id'],
            name=item.get('title') or item.get('name') or '',
            slug=item.get('slug'),
            min_price=int(item.get('min_price', 0) or 0),
            has_stock=True,
            images=images,
        )

    @staticmethod
    def _product_id(product: dict[str, Any]) -> str | None:
        raw = product.get('id')
        return str(raw) if raw is not None else None

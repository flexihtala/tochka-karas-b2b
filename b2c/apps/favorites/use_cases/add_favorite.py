from uuid import UUID

from apps.favorites.errors import B2BUnavailableError, ProductNotFoundError
from apps.favorites.repositories import FavoriteRepository
from apps.favorites.schemas.db import FavoriteCreateSchema
from apps.favorites.use_cases.list_favorites import B2BProductsClient
from shared.auth_lib import AuthenticatedUserSchema
from shared.http_clients import ServiceClientError


class AddFavoriteUseCase:
    """PUT /api/v1/favorites/{product_id} — идемпотентное добавление товара в избранное.

    Бизнес-правила:
    - user_id ВСЕГДА берётся из JWT (current_user.id) — защита от IDOR.
    - Валидация существования товара через B2B: неизвестный/заблокированный/
      удалённый товар → ProductNotFoundError (404).
    - Идемпотентность: повторное добавление того же (user_id, product_id)
      не создаёт дубль; роутер в обоих случаях отвечает 204 без тела.
    """

    def __init__(self, favorite_repository: FavoriteRepository, b2b_products_client: B2BProductsClient):
        self.favorite_repository = favorite_repository
        self.b2b_products_client = b2b_products_client

    async def __call__(self, product_id: UUID, current_user: AuthenticatedUserSchema) -> None:
        await self._ensure_product_exists(product_id)

        existing = await self.favorite_repository.get_by_user_and_product(
            current_user.id,
            product_id,
        )
        if existing is not None:
            return

        await self.favorite_repository.create(
            FavoriteCreateSchema(
                user_id=current_user.id,
                product_id=product_id,
            )
        )

    async def _ensure_product_exists(self, product_id: UUID) -> None:
        """Неизвестный товар → 404; B2B недоступен → 503 (PUT не деградирует)."""
        try:
            products = await self.b2b_products_client.list_products_by_ids([product_id])
        except ServiceClientError as exc:
            raise B2BUnavailableError() from exc
        if not products:
            raise ProductNotFoundError()

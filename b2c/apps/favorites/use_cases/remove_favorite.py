from uuid import UUID

from apps.favorites.repositories import FavoriteRepository
from shared.auth_lib import AuthenticatedUserSchema


class RemoveFavoriteUseCase:
    """DELETE /api/v1/favorites/{product_id} — удаление товара из избранного.

    Бизнес-правила:
    - user_id ВСЕГДА берётся из JWT (current_user.id).
    - Удаление чужой пары (user_id, product_id) физически невозможно: WHERE
      user_id = current_user.id. Это автоматически защищает от IDOR.
    - Идемпотентность: удаление несуществующей пары возвращается 204 без ошибки.
    """

    def __init__(self, favorite_repository: FavoriteRepository):
        self.favorite_repository = favorite_repository

    async def __call__(self, product_id: UUID, current_user: AuthenticatedUserSchema) -> None:
        await self.favorite_repository.delete_by_user_and_product(
            current_user.id,
            product_id,
        )

from dataclasses import dataclass

from apps.favorites.repositories import FavoriteRepository
from apps.favorites.schemas.db import FavoriteCreateSchema
from apps.favorites.schemas.request import AddFavoriteRequestSchema
from apps.favorites.schemas.response import FavoriteResponseSchema
from shared.auth_lib import AuthenticatedUserSchema


@dataclass(slots=True)
class FavoriteCreatedResult:
    """Результат добавления: схема + флаг "создано впервые"
    (для маппинга на 201 vs 200 в роутере).
    """

    favorite: FavoriteResponseSchema
    created: bool


class AddFavoriteUseCase:
    """POST /api/v1/favorites — добавление товара в избранное.

    Бизнес-правила:
    - user_id ВСЕГДА берётся из JWT (current_user.id). Любой user_id в теле/query
      игнорируется на уровне схемы запроса (extra='ignore').
    - Идемпотентность: повторное добавление того же (user_id, product_id)
      возвращает существующую запись с флагом created=False — роутер ответит 200.
    - При первом добавлении created=True — роутер ответит 201.
    """

    def __init__(self, favorite_repository: FavoriteRepository):
        self.favorite_repository = favorite_repository

    async def __call__(
        self,
        data: AddFavoriteRequestSchema,
        current_user: AuthenticatedUserSchema,
    ) -> FavoriteCreatedResult:
        existing = await self.favorite_repository.get_by_user_and_product(
            current_user.id,
            data.product_id,
        )
        if existing is not None:
            return FavoriteCreatedResult(
                favorite=FavoriteResponseSchema.model_validate(existing),
                created=False,
            )

        favorite = await self.favorite_repository.create(
            FavoriteCreateSchema(
                user_id=current_user.id,
                product_id=data.product_id,
            )
        )
        return FavoriteCreatedResult(
            favorite=FavoriteResponseSchema.model_validate(favorite),
            created=True,
        )

from uuid import UUID

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Response, status

from apps.auth.schemas import ErrorResponseSchema
from apps.favorites.schemas.request import AddFavoriteRequestSchema
from apps.favorites.schemas.response import FavoriteListResponseSchema, FavoriteResponseSchema
from apps.favorites.use_cases import (
    AddFavoriteUseCase,
    ListFavoritesUseCase,
    RemoveFavoriteUseCase,
)
from shared.auth_lib import AuthenticatedUserSchema, UserRole, require_role

router = APIRouter(prefix='/favorites')


error_responses = {
    400: {'model': ErrorResponseSchema},
    401: {'model': ErrorResponseSchema},
    403: {'model': ErrorResponseSchema},
    404: {'model': ErrorResponseSchema},
    503: {'model': ErrorResponseSchema},
}


@router.get('', response_model=FavoriteListResponseSchema, responses=error_responses)
@inject
async def list_favorites(
    use_case: FromDishka[ListFavoritesUseCase],
    current_user: AuthenticatedUserSchema = Depends(require_role(UserRole.BUYER)),
) -> FavoriteListResponseSchema:
    return await use_case(current_user)


@router.post(
    '/{product_id}',
    response_model=FavoriteResponseSchema,
    responses=error_responses,
)
@inject
async def add_favorite(
    product_id: UUID,
    use_case: FromDishka[AddFavoriteUseCase],
    response: Response,
    current_user: AuthenticatedUserSchema = Depends(require_role(UserRole.BUYER)),
) -> FavoriteResponseSchema:
    """POST /api/v1/favorites/{product_id} — добавление товара в избранное.

    Канон b2c-cart-flows#b2c-6-favorites: **201 при первом добавлении, 200 при
    повторном** (идемпотентно — не 409, не дубль в БД). user_id — ТОЛЬКО из JWT,
    любой user_id в теле/query игнорируется (см. ADR).
    """
    result = await use_case(AddFavoriteRequestSchema(product_id=product_id), current_user)
    response.status_code = status.HTTP_201_CREATED if result.created else status.HTTP_200_OK
    return result.favorite


@router.delete('/{product_id}', status_code=status.HTTP_204_NO_CONTENT, responses=error_responses)
@inject
async def remove_favorite(
    product_id: UUID,
    use_case: FromDishka[RemoveFavoriteUseCase],
    current_user: AuthenticatedUserSchema = Depends(require_role(UserRole.BUYER)),
) -> Response:
    """DELETE /api/v1/favorites/{product_id} — удаление из избранного.

    Идемпотентно: 204 даже если ничего не было удалено.
    user_id — ТОЛЬКО из JWT (любая попытка удалить чужое физически невозможна).
    """
    await use_case(product_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

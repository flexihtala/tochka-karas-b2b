from uuid import UUID

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Query, Response, status

from apps.auth.schemas import ErrorResponseSchema
from apps.catalog.schemas import CatalogPaginatedResponseSchema
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


@router.get('', response_model=CatalogPaginatedResponseSchema, responses=error_responses)
@inject
async def list_favorites(
    use_case: FromDishka[ListFavoritesUseCase],
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: AuthenticatedUserSchema = Depends(require_role(UserRole.BUYER)),
) -> CatalogPaginatedResponseSchema:
    """GET /api/v1/favorites — избранное в формате PaginatedCatalogProducts.

    {items, total_count, limit, offset}, items — CatalogProductCard.
    total_count — общее число избранного (до обогащения B2B). Если B2B недоступен,
    отдаём 200 с исключением необогащённых товаров из items (деградация, не 5xx).
    """
    return await use_case(current_user, limit=limit, offset=offset)


@router.put('/{product_id}', status_code=status.HTTP_204_NO_CONTENT, responses=error_responses)
@inject
async def add_favorite(
    product_id: UUID,
    use_case: FromDishka[AddFavoriteUseCase],
    current_user: AuthenticatedUserSchema = Depends(require_role(UserRole.BUYER)),
) -> Response:
    """PUT /api/v1/favorites/{product_id} — добавление товара в избранное.

    Идемпотентно: **204 No Content без тела** и при первом, и при повторном
    добавлении (не 409, не дубль в БД). Неизвестный товар → 404.
    user_id — ТОЛЬКО из JWT, любой user_id в теле/query игнорируется (см. ADR).
    """
    await use_case(product_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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

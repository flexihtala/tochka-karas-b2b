from uuid import UUID

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Request, Response, status

from apps.auth.schemas import ErrorResponseSchema
from apps.home.schemas import (
    BannerClickRequestSchema,
    BannerListResponseSchema,
    CollectionMetaResponseSchema,
    CollectionProductsResponseSchema,
)
from apps.home.use_cases import (
    ClickBannerUseCase,
    GetCollectionProductsUseCase,
    ListBannersUseCase,
    ListCollectionsUseCase,
)
from shared.auth_lib import AuthenticatedUserSchema

router = APIRouter()


error_responses = {
    400: {'model': ErrorResponseSchema},
    404: {'model': ErrorResponseSchema},
}


@router.get(
    '/home/banners',
    response_model=BannerListResponseSchema,
    responses=error_responses,
)
@inject
async def list_home_banners(use_case: FromDishka[ListBannersUseCase]) -> BannerListResponseSchema:
    """GET /api/v1/home/banners — публичный список активных баннеров (канон B2C-14)."""
    return await use_case()


@router.post(
    '/banner-events',
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses,
)
@inject
async def post_banner_event(
    data: BannerClickRequestSchema,
    use_case: FromDishka[ClickBannerUseCase],
    request: Request,
) -> Response:
    user: AuthenticatedUserSchema | None = getattr(request.state, 'user', None)
    await use_case(data, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    '/catalog/collections',
    response_model=list[CollectionMetaResponseSchema],
    responses=error_responses,
)
@inject
async def list_home_collections(
    use_case: FromDishka[ListCollectionsUseCase],
) -> list[CollectionMetaResponseSchema]:
    """GET /api/v1/catalog/collections — список подборок без товаров (spec-путь)."""
    return await use_case()


@router.get(
    '/home/collections',
    response_model=list[CollectionMetaResponseSchema],
    responses=error_responses,
)
@inject
async def list_home_collections_alias(
    use_case: FromDishka[ListCollectionsUseCase],
) -> list[CollectionMetaResponseSchema]:
    """GET /api/v1/home/collections — alias канонного пути (B2C-15)."""
    return await use_case()


@router.get(
    '/catalog/collections/{collection_id}/products',
    response_model=CollectionProductsResponseSchema,
    responses=error_responses,
)
@inject
async def get_home_collection_products(
    collection_id: UUID,
    use_case: FromDishka[GetCollectionProductsUseCase],
) -> CollectionProductsResponseSchema:
    """GET /api/v1/catalog/collections/{id}/products — товары подборки.

    Spec встраивает products внутрь Collection; раздельный endpoint ограничивает
    размер ответа и отделяет листинг метаданных от B2B-обогащения (канон B2C-15:
    items в исходном порядке + unavailable_ids).
    """
    return await use_case(collection_id)


@router.get(
    '/home/collections/{collection_id}/products',
    response_model=CollectionProductsResponseSchema,
    responses=error_responses,
)
@inject
async def get_home_collection_products_alias(
    collection_id: UUID,
    use_case: FromDishka[GetCollectionProductsUseCase],
) -> CollectionProductsResponseSchema:
    """GET /api/v1/home/collections/{id}/products — alias канонного пути (B2C-15)."""
    return await use_case(collection_id)

from uuid import UUID

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Request, Response, status

from apps.auth.schemas import ErrorResponseSchema
from apps.home.schemas import (
    BannerClickRequestSchema,
    BannerResponseSchema,
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
    '/catalog/banners',
    response_model=list[BannerResponseSchema],
    responses=error_responses,
)
@inject
async def list_home_banners(use_case: FromDishka[ListBannersUseCase]) -> list[BannerResponseSchema]:
    """GET /api/v1/catalog/banners — active banners per openapi spec."""
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
    """GET /api/v1/catalog/collections — collections list per openapi spec."""
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
    """GET /api/v1/catalog/collections/{id}/products — project extension.

    Spec embeds products inside Collection; this split endpoint keeps the
    response size bounded and decouples meta-listing from B2B enrichment.
    """
    return await use_case(collection_id)

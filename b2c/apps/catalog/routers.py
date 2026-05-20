"""US-CAT-01: маршруты каталога (листинг + фасеты).

Эндпоинты публичные — JWT не требуется (canon: каталог открыт для незарегистрированных).
"""

from uuid import UUID

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Query

from apps.auth.schemas import ErrorResponseSchema
from apps.catalog.schemas import (
    CatalogFacetsResponseSchema,
    CatalogPaginatedResponseSchema,
    CatalogProductDetailResponseSchema,
)
from apps.catalog.use_cases import GetFacetsUseCase, GetProductUseCase, GetSimilarUseCase, ListProductsUseCase

router = APIRouter()


error_responses = {
    400: {'model': ErrorResponseSchema},
    404: {'model': ErrorResponseSchema},
    502: {'model': ErrorResponseSchema},
}


@router.get(
    '/products',
    response_model=CatalogPaginatedResponseSchema,
    responses=error_responses,
)
@inject
async def list_products(
    use_case: FromDishka[ListProductsUseCase],
    category_id: UUID | None = Query(default=None),
    price_min: int | None = Query(default=None, ge=0),
    price_max: int | None = Query(default=None, ge=0),
    sort: str | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> CatalogPaginatedResponseSchema:
    return await use_case(
        category_id=category_id,
        price_min=price_min,
        price_max=price_max,
        sort=sort,
        search=search,
        limit=limit,
        offset=offset,
    )


@router.get(
    '/catalog/facets',
    response_model=CatalogFacetsResponseSchema,
    responses=error_responses,
)
@inject
async def get_facets(
    use_case: FromDishka[GetFacetsUseCase],
    category_id: UUID | None = Query(default=None),
    price_min: int | None = Query(default=None, ge=0),
    price_max: int | None = Query(default=None, ge=0),
) -> CatalogFacetsResponseSchema:
    return await use_case(
        category_id=category_id,
        price_min=price_min,
        price_max=price_max,
    )


@router.get(
    '/products/{product_id}',
    response_model=CatalogProductDetailResponseSchema,
    responses=error_responses,
)
@inject
async def get_product(
    product_id: UUID,
    use_case: FromDishka[GetProductUseCase],
) -> CatalogProductDetailResponseSchema:
    return await use_case(product_id)


@router.get(
    '/products/{product_id}/similar',
    response_model=CatalogPaginatedResponseSchema,
    responses=error_responses,
)
@inject
async def get_similar_products(
    product_id: UUID,
    use_case: FromDishka[GetSimilarUseCase],
    limit: int = Query(default=8, ge=1, le=20),
    offset: int = Query(default=0, ge=0),
) -> CatalogPaginatedResponseSchema:
    return await use_case(product_id, limit=limit, offset=offset)

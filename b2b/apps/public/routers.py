"""US-B2B-07: Public Catalog — service-to-service витрина для B2C.

Auth: только X-Service-Key (направление b2c_to_b2b). JWT не используется → без
ключа любой эндпоинт отвечает 401.

5 эндпоинтов по OpenAPI (tags: Public Catalog, paths /api/v1/public/...):
  1. GET  /public/products              — листинг коротких карточек + фильтры/сортировка.
  2. POST /public/products/batch        — карточки по списку id (видимое подмножество).
  3. GET  /public/products/{id}         — полная карточка (404 если не видим).
  4. GET  /public/products/{id}/similar — похожие (та же категория, случайно).
  5. GET  /public/skus/{id}             — SKU витрины (404 если товар не видим).

Видимость везде: status == MODERATED, deleted == false, есть SKU active_quantity > 0.
"""

import re
from uuid import UUID

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Query, Request, status

from apps.auth.schemas import ErrorResponseSchema
from apps.public.enums import CatalogSort
from apps.public.schemas.request import BatchProductsRequestSchema
from apps.public.schemas.response import (
    ProductPublicPaginatedResponseSchema,
    ProductPublicResponseSchema,
    ProductPublicShortResponseSchema,
    SKUPublicResponseSchema,
)
from apps.public.use_cases import (
    BatchProductsUseCase,
    GetPublicProductUseCase,
    GetPublicSKUUseCase,
    GetSimilarProductsUseCase,
    ListCatalogUseCase,
)
from settings import settings
from shared.inbox.dependencies import make_verify_service_key
from shared.types import ServiceKeyDirection

router = APIRouter(prefix='/public')

verify_b2c_to_b2b = make_verify_service_key(ServiceKeyDirection.B2C_TO_B2B, settings.b2c_to_b2b_key)


error_responses = {
    400: {'model': ErrorResponseSchema},
    401: {'model': ErrorResponseSchema},
}

get_error_responses = {
    401: {'model': ErrorResponseSchema},
    404: {'model': ErrorResponseSchema},
}


_FILTER_KEY_RE = re.compile(r'^filters\[(?P<key>[^\]]+)\]$')


def _parse_filters(request: Request) -> dict[str, list[str]]:
    """Парсит deepObject-параметры ?filters[key]=value в dict[key, list[value]].

    Поддерживает повтор ключа (explode: true): ?filters[brand]=apple&filters[brand]=samsung
    → {'brand': ['apple', 'samsung']}. Ключи берутся как есть (snake_case).
    Значения всегда строки (number/bool в URL приходят строками).
    """
    result: dict[str, list[str]] = {}
    for raw_key, value in request.query_params.multi_items():
        match = _FILTER_KEY_RE.match(raw_key)
        if match is None:
            continue
        result.setdefault(match.group('key'), []).append(value)
    return result


@router.get(
    '/products',
    status_code=status.HTTP_200_OK,
    response_model=ProductPublicPaginatedResponseSchema,
    response_model_exclude_none=False,
    responses=error_responses,
    dependencies=[Depends(verify_b2c_to_b2b)],
)
@inject
async def list_catalog_products(
    request: Request,
    use_case: FromDishka[ListCatalogUseCase],
    category_id: UUID | None = Query(default=None),
    search: str | None = Query(default=None, min_length=3),
    min_price: int | None = Query(default=None, ge=0),
    max_price: int | None = Query(default=None, ge=0),
    seller_id: UUID | None = Query(default=None),
    sort: CatalogSort = Query(default=CatalogSort.CREATED_DESC),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ProductPublicPaginatedResponseSchema:
    return await use_case(
        category_id=category_id,
        search=search,
        min_price=min_price,
        max_price=max_price,
        seller_id=seller_id,
        filters=_parse_filters(request) or None,
        sort=sort,
        limit=limit,
        offset=offset,
    )


@router.post(
    '/products/batch',
    status_code=status.HTTP_200_OK,
    response_model=list[ProductPublicResponseSchema],
    responses=error_responses,
    dependencies=[Depends(verify_b2c_to_b2b)],
)
@inject
async def batch_catalog_products(
    data: BatchProductsRequestSchema,
    use_case: FromDishka[BatchProductsUseCase],
) -> list[ProductPublicResponseSchema]:
    return await use_case(product_ids=data.product_ids)


@router.get(
    '/products/{product_id}',
    status_code=status.HTTP_200_OK,
    response_model=ProductPublicResponseSchema,
    responses=get_error_responses,
    dependencies=[Depends(verify_b2c_to_b2b)],
)
@inject
async def get_catalog_product(
    product_id: UUID,
    use_case: FromDishka[GetPublicProductUseCase],
) -> ProductPublicResponseSchema:
    return await use_case(product_id)


@router.get(
    '/products/{product_id}/similar',
    status_code=status.HTTP_200_OK,
    response_model=list[ProductPublicShortResponseSchema],
    responses=error_responses,
    dependencies=[Depends(verify_b2c_to_b2b)],
)
@inject
async def get_catalog_similar_products(
    product_id: UUID,
    use_case: FromDishka[GetSimilarProductsUseCase],
    limit: int = Query(default=10, ge=1, le=50),
) -> list[ProductPublicShortResponseSchema]:
    return await use_case(product_id, limit=limit)


@router.get(
    '/skus/{sku_id}',
    status_code=status.HTTP_200_OK,
    response_model=SKUPublicResponseSchema,
    responses=get_error_responses,
    dependencies=[Depends(verify_b2c_to_b2b)],
)
@inject
async def get_catalog_sku(
    sku_id: UUID,
    use_case: FromDishka[GetPublicSKUUseCase],
) -> SKUPublicResponseSchema:
    return await use_case(sku_id)

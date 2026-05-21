from uuid import UUID

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Query

from apps.auth.schemas import ErrorResponseSchema
from apps.categories.schemas import (
    BreadcrumbsResponseSchema,
    CategoryResponseSchema,
    CategoryTreeNodeSchema,
    CategoryTreeResponseSchema,
)
from apps.categories.use_cases import (
    GetBreadcrumbsUseCase,
    GetCategoryUseCase,
    GetTreeUseCase,
)

router = APIRouter(prefix='/catalog/categories', tags=['Categories'])


error_responses = {
    400: {'model': ErrorResponseSchema},
    404: {'model': ErrorResponseSchema},
    422: {'model': ErrorResponseSchema},
}


@router.get(
    '/tree',
    response_model=list[CategoryTreeNodeSchema],
    responses={422: {'model': ErrorResponseSchema}},
)
@inject
async def get_categories_tree(
    use_case: FromDishka[GetTreeUseCase],
) -> list[CategoryTreeNodeSchema]:
    """GET /api/v1/catalog/categories/tree — flat array of root nodes per openapi spec."""
    response: CategoryTreeResponseSchema = await use_case()
    return response.items


@router.get(
    '/breadcrumbs',
    response_model=BreadcrumbsResponseSchema,
    responses=error_responses,
)
@inject
async def get_breadcrumbs(
    use_case: FromDishka[GetBreadcrumbsUseCase],
    category_id: UUID | None = Query(default=None),
    product_id: UUID | None = Query(default=None),
) -> BreadcrumbsResponseSchema:
    """Хлебные крошки от корня до категории/товара. Публичный эндпоинт.

    Ровно один параметр: category_id или product_id (иначе 400).
    """
    return await use_case(category_id=category_id, product_id=product_id)


@router.get(
    '/{category_id}',
    response_model=CategoryResponseSchema,
    responses={404: {'model': ErrorResponseSchema}},
)
@inject
async def get_category(
    category_id: UUID,
    use_case: FromDishka[GetCategoryUseCase],
) -> CategoryResponseSchema:
    """Детали одной категории. Публичный эндпоинт."""
    return await use_case(category_id)

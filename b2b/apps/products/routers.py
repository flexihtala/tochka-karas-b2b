from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Query, status

from apps.auth.schemas import ErrorResponseSchema
from apps.products.enums import ProductStatus
from apps.products.schemas.request import ProductCreateRequestSchema
from apps.products.schemas.response import ProductPaginatedResponseSchema, ProductResponseSchema
from apps.products.use_cases import CreateProductUseCase, ListSellerProductsUseCase
from shared.auth_lib import AuthenticatedUserSchema, UserRole, require_role

router = APIRouter(prefix='/products')


error_responses = {
    400: {'model': ErrorResponseSchema},
    401: {'model': ErrorResponseSchema},
    403: {'model': ErrorResponseSchema},
}


@router.post(
    '',
    status_code=status.HTTP_201_CREATED,
    response_model=ProductResponseSchema,
    responses=error_responses,
)
@inject
async def create_product(
    data: ProductCreateRequestSchema,
    use_case: FromDishka[CreateProductUseCase],
    current_user: AuthenticatedUserSchema = Depends(require_role(UserRole.SELLER)),
) -> ProductResponseSchema:
    return await use_case(data, current_user)


@router.get(
    '',
    status_code=status.HTTP_200_OK,
    response_model=ProductPaginatedResponseSchema,
    responses=error_responses,
)
@inject
async def list_my_products(
    use_case: FromDishka[ListSellerProductsUseCase],
    current_user: AuthenticatedUserSchema = Depends(require_role(UserRole.SELLER)),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status_filter: ProductStatus | None = Query(default=None, alias='status'),
    include_deleted: bool = Query(default=False),
    search: str | None = Query(default=None, max_length=255),
) -> ProductPaginatedResponseSchema:
    """B2B-11: список своих товаров.

    Бизнес-правила:
    - seller_id берётся ТОЛЬКО из JWT (current_user.id). Параметр `?seller_id=` намеренно
      не объявлен — он будет проигнорирован FastAPI как неизвестный query-параметр (защита от IDOR).
    - По умолчанию возвращаются только не удалённые товары; `?include_deleted=true` снимает фильтр.
    - Фильтр `?status=` принимает значения ProductStatus enum.
    - Поиск `?search=` — case-insensitive ILIKE по title.
    """
    return await use_case(
        current_user=current_user,
        limit=limit,
        offset=offset,
        status=status_filter,
        include_deleted=include_deleted,
        search=search,
    )
